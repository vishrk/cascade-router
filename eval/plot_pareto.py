"""Sweeps a few heuristic thresholds and plots accuracy vs. total cost — the
first real Pareto curve, backed by actual API calls and LLM-judge grading
rather than assumption. For each question, both tiers' response are needed
at least once across the sweep (cached in eval/tier_results.json, keyed by
question+model, so re-running or sweeping more thresholds never re-calls a
tier that's already been evaluated for that question).
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
from pricing import calculate_cost
from run_eval import grade
from scorer import extract_features, score_from_features

load_dotenv()

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "dataset.json"
TIER_RESULTS_PATH = EVAL_DIR / "tier_results.json"
CHART_PATH = EVAL_DIR / "pareto_v1.png"

THRESHOLDS = [0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0]


def load_tier_results() -> dict:
    if TIER_RESULTS_PATH.exists():
        return json.loads(TIER_RESULTS_PATH.read_text())
    return {}


def save_tier_results(results: dict) -> None:
    TIER_RESULTS_PATH.write_text(json.dumps(results, indent=2))


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
    save_tier_results(results)
    return results[key]


def main():
    dataset = json.loads(DATASET_PATH.read_text())["questions"]
    tier_results = load_tier_results()
    client = Anthropic()

    scored = [(q, score_from_features(extract_features(q["prompt"]))) for q in dataset]

    needed = sum(
        1
        for q, score in scored
        for model in ({EXPENSIVE_MODEL if score >= t else CHEAP_MODEL for t in THRESHOLDS})
        if f"{q['id']}::{model}" not in tier_results
    )
    print(f"{len(tier_results)} tier results cached, {needed} calls needed for this sweep")

    for q, score in scored:
        for model in {EXPENSIVE_MODEL if score >= t else CHEAP_MODEL for t in THRESHOLDS}:
            get_tier_result(client, tier_results, q["id"], q["prompt"], model)

    points = []
    for threshold in THRESHOLDS:
        correct_count = 0
        total_cost = 0.0
        for q, score in scored:
            model = EXPENSIVE_MODEL if score >= threshold else CHEAP_MODEL
            result = tier_results[f"{q['id']}::{model}"]
            correct_count += int(result["correct"])
            total_cost += result["cost_usd"]
        accuracy = correct_count / len(scored)
        points.append({"threshold": threshold, "accuracy": accuracy, "total_cost": total_cost})
        print(f"threshold={threshold:.2f}  accuracy={accuracy:.1%}  total_cost=${total_cost:.4f}")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot([p["total_cost"] for p in points], [p["accuracy"] for p in points], marker="o")
    for p in points:
        ax.annotate(f"t={p['threshold']}", (p["total_cost"], p["accuracy"]), textcoords="offset points", xytext=(6, 4))
    ax.set_xlabel("Total cost ($)")
    ax.set_ylabel("Accuracy")
    ax.set_title("Cascade Router v1 (heuristic) — accuracy vs. cost by threshold")
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    print(f"Chart saved to {CHART_PATH}")


if __name__ == "__main__":
    main()
