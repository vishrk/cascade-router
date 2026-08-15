"""Sweeps a few thresholds for both routers and plots accuracy vs. total cost
on one chart — the heuristic router (v1, score threshold) against the cascade
router (self-consistency confidence threshold), backed by actual API calls
and LLM-judge grading rather than assumption.

Every per-question result is cached (tier_results.json for the heuristic
sweep, cascade_results.json for the cascade sweep) so re-running or sweeping
more thresholds never re-calls something already evaluated for that question.
Run: python eval/plot_pareto.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import matplotlib.pyplot as plt
from anthropic import Anthropic
from dotenv import load_dotenv

from app import CHEAP_MODEL, EXPENSIVE_MAX_TOKENS, EXPENSIVE_MODEL, MAX_TOKENS
from confidence import self_consistency_confidence
from pricing import calculate_cost
from run_eval import grade
from scorer import extract_features, score_from_features

load_dotenv()

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "dataset.json"
TIER_RESULTS_PATH = EVAL_DIR / "tier_results.json"
CASCADE_RESULTS_PATH = EVAL_DIR / "cascade_results.json"
CHART_PATH = EVAL_DIR / "pareto.png"

HEURISTIC_THRESHOLDS = [0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]
CASCADE_THRESHOLDS = [0.34, 0.67, 1.0]  # any agreement / majority / unanimous


# --- heuristic router (v1: score threshold) ---


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


def get_tier_result(client: Anthropic, results: dict, question_id: str, prompt: str, model: str) -> dict:
    key = f"{question_id}::{model}"
    if key in results:
        return results[key]

    max_tokens = EXPENSIVE_MAX_TOKENS if model == EXPENSIVE_MODEL else MAX_TOKENS
    reply = client.messages.create(model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
    text = "".join(block.text for block in reply.content if block.type == "text")
    grade_result = grade(client, prompt, text) if text else None

    results[key] = {
        "correct": grade_result.correct if grade_result else False,
        "cost_usd": calculate_cost(model, reply.usage.input_tokens, reply.usage.output_tokens),
    }
    save_json(TIER_RESULTS_PATH, results)
    return results[key]


def heuristic_points(client: Anthropic, scored: list) -> list:
    tier_results = load_json(TIER_RESULTS_PATH)

    for q, score in scored:
        for model in {EXPENSIVE_MODEL if score >= t else CHEAP_MODEL for t in HEURISTIC_THRESHOLDS}:
            get_tier_result(client, tier_results, q["id"], q["prompt"], model)

    points = []
    for threshold in HEURISTIC_THRESHOLDS:
        correct_count = 0
        total_cost = 0.0
        for q, score in scored:
            model = EXPENSIVE_MODEL if score >= threshold else CHEAP_MODEL
            result = tier_results[f"{q['id']}::{model}"]
            correct_count += int(result["correct"])
            total_cost += result["cost_usd"]
        points.append({"label": f"t={threshold}", "accuracy": correct_count / len(scored), "total_cost": total_cost})
    return points


# --- cascade router (cheap-first, escalate on low self-consistency confidence) ---


def get_cascade_signal(client: Anthropic, results: dict, question_id: str, prompt: str) -> dict:
    if question_id in results and "confidence" in results[question_id]:
        return results[question_id]

    signal = self_consistency_confidence(client, CHEAP_MODEL, prompt, n=3, max_tokens=MAX_TOKENS)
    cheap_cost = sum(calculate_cost(CHEAP_MODEL, i, o) for i, o in signal["usage"])
    grade_result = grade(client, prompt, signal["representative"]) if signal["representative"] else None

    entry = results.setdefault(question_id, {})
    entry.update(
        {
            "confidence": signal["confidence"],
            "cheap_cost": cheap_cost,
            "cheap_correct": grade_result.correct if grade_result else False,
        }
    )
    save_json(CASCADE_RESULTS_PATH, results)
    return entry


def get_cascade_expensive(client: Anthropic, results: dict, question_id: str, prompt: str) -> dict:
    entry = results[question_id]
    if "expensive_cost" in entry:
        return entry

    reply = client.messages.create(
        model=EXPENSIVE_MODEL, max_tokens=EXPENSIVE_MAX_TOKENS, messages=[{"role": "user", "content": prompt}]
    )
    text = "".join(block.text for block in reply.content if block.type == "text")
    grade_result = grade(client, prompt, text) if text else None

    entry.update(
        {
            "expensive_cost": calculate_cost(EXPENSIVE_MODEL, reply.usage.input_tokens, reply.usage.output_tokens),
            "expensive_correct": grade_result.correct if grade_result else False,
        }
    )
    save_json(CASCADE_RESULTS_PATH, results)
    return entry


def cascade_points(client: Anthropic, dataset: list) -> list:
    cascade_results = load_json(CASCADE_RESULTS_PATH)

    for q in dataset:
        get_cascade_signal(client, cascade_results, q["id"], q["prompt"])

    points = []
    for threshold in CASCADE_THRESHOLDS:
        correct_count = 0
        total_cost = 0.0
        for q in dataset:
            entry = cascade_results[q["id"]]
            escalate = entry["confidence"] < threshold
            if escalate:
                entry = get_cascade_expensive(client, cascade_results, q["id"], q["prompt"])
                correct_count += int(entry["expensive_correct"])
                total_cost += entry["cheap_cost"] + entry["expensive_cost"]
            else:
                correct_count += int(entry["cheap_correct"])
                total_cost += entry["cheap_cost"]
        points.append(
            {"label": f"c>={threshold}", "accuracy": correct_count / len(dataset), "total_cost": total_cost}
        )
    return points


def plot(ax, points: list, label: str, color: str) -> None:
    ax.plot(
        [p["total_cost"] for p in points],
        [p["accuracy"] for p in points],
        marker="o",
        label=label,
        color=color,
    )
    for p in points:
        ax.annotate(p["label"], (p["total_cost"], p["accuracy"]), textcoords="offset points", xytext=(6, 4))


def main():
    dataset = json.loads(DATASET_PATH.read_text())["questions"]
    client = Anthropic()

    scored = [(q, score_from_features(extract_features(q["prompt"]))) for q in dataset]

    h_points = heuristic_points(client, scored)
    print("Heuristic router (v1):")
    for p in h_points:
        print(f"  {p['label']:>8}  accuracy={p['accuracy']:.1%}  total_cost=${p['total_cost']:.4f}")

    c_points = cascade_points(client, dataset)
    print("Cascade router:")
    for p in c_points:
        print(f"  {p['label']:>8}  accuracy={p['accuracy']:.1%}  total_cost=${p['total_cost']:.4f}")

    fig, ax = plt.subplots(figsize=(7, 5))
    plot(ax, h_points, "Heuristic (v1)", "tab:blue")
    plot(ax, c_points, "Cascade", "tab:orange")
    ax.set_xlabel("Total cost ($)")
    ax.set_ylabel("Accuracy")
    ax.set_title("Cascade Router — accuracy vs. cost, heuristic vs. cascade")
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    print(f"Chart saved to {CHART_PATH}")


if __name__ == "__main__":
    main()
