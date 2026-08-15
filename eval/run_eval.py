"""Runs dataset.json through the Phase 1 heuristic router for real, and grades
each response for correctness with an LLM judge. Logs per-question: predicted
tier, ground-truth difficulty label, whether the answer was actually correct,
and real cost. Resumable — re-running skips already-evaluated questions.
Requires eval/labels.json (run label_dataset.py first).
Run: python eval/run_eval.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from app import CHEAP_MODEL, EXPENSIVE_MAX_TOKENS, EXPENSIVE_MODEL, MAX_TOKENS, THRESHOLD
from pricing import calculate_cost
from scorer import extract_features, score_from_features

load_dotenv()

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "dataset.json"
LABELS_PATH = EVAL_DIR / "labels.json"
RESULTS_PATH = EVAL_DIR / "results.json"

GRADING_RUBRIC = """You are grading whether a response correctly and adequately
answers the given question. Judge on substance, not style or length.
Respond with whether the response is correct and a one-sentence reasoning."""


class CorrectnessGrade(BaseModel):
    correct: bool
    reasoning: str


def load_results() -> dict:
    if RESULTS_PATH.exists():
        return json.loads(RESULTS_PATH.read_text())["results"]
    return {}


def save_results(results: dict) -> None:
    RESULTS_PATH.write_text(json.dumps({"threshold": THRESHOLD, "results": results}, indent=2))


def grade(client: Anthropic, prompt: str, response_text: str) -> CorrectnessGrade:
    graded = client.messages.parse(
        model=EXPENSIVE_MODEL,
        max_tokens=EXPENSIVE_MAX_TOKENS,
        system=GRADING_RUBRIC,
        messages=[{"role": "user", "content": f"Question: {prompt}\n\nResponse: {response_text}"}],
        output_format=CorrectnessGrade,
    )
    return graded.parsed_output


def main():
    dataset = json.loads(DATASET_PATH.read_text())["questions"]
    if not LABELS_PATH.exists():
        sys.exit("eval/labels.json not found — run `python eval/label_dataset.py` first.")
    labels = json.loads(LABELS_PATH.read_text())["labels"]

    results = load_results()
    client = Anthropic()

    remaining = [q for q in dataset if q["id"] not in results]
    print(f"{len(results)} already evaluated, {len(remaining)} to go")

    for i, q in enumerate(remaining, 1):
        features = extract_features(q["prompt"])
        score = score_from_features(features)
        model = EXPENSIVE_MODEL if score >= THRESHOLD else CHEAP_MODEL
        max_tokens = EXPENSIVE_MAX_TOKENS if model == EXPENSIVE_MODEL else MAX_TOKENS

        start = time.monotonic()
        reply = client.messages.create(
            model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": q["prompt"]}]
        )
        latency_ms = (time.monotonic() - start) * 1000
        text = "".join(block.text for block in reply.content if block.type == "text")

        grade_result = grade(client, q["prompt"], text) if text else CorrectnessGrade(correct=False, reasoning="empty response")

        cost = calculate_cost(model, reply.usage.input_tokens, reply.usage.output_tokens)

        results[q["id"]] = {
            "score": score,
            "predicted_tier": "expensive" if model == EXPENSIVE_MODEL else "cheap",
            "model": model,
            "ground_truth_difficulty": labels.get(q["id"], {}).get("difficulty"),
            "correct": grade_result.correct,
            "cost_usd": cost,
            "latency_ms": latency_ms,
        }
        save_results(results)
        print(f"[{i}/{len(remaining)}] {q['id']}: {model} correct={grade_result.correct} cost=${cost:.6f}")

    print(f"Done. {len(results)} results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
