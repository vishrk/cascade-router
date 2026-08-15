"""LLM-as-judge labeling: rates every question in dataset.json for difficulty
on a fixed rubric using a strong model. Resumable — re-running skips
already-labeled questions. Run: python eval/label_dataset.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

EVAL_DIR = Path(__file__).resolve().parent
DATASET_PATH = EVAL_DIR / "dataset.json"
LABELS_PATH = EVAL_DIR / "labels.json"
JUDGE_MODEL = os.environ.get("EXPENSIVE_MODEL", "claude-opus-5")

RUBRIC = """Rate the complexity of the given question on a fixed 1-5 scale:

1 = Trivial factual recall or single-step arithmetic. No reasoning required.
2 = Simple task requiring basic knowledge or a short explanation, still single-step.
3 = Moderate: requires multi-step reasoning, synthesis of a few facts, or a short code/math task.
4 = Complex: multi-step reasoning, domain expertise, or a non-trivial implementation/proof.
5 = Expert-level: deep reasoning, formal proofs, system design, or extensive multi-step analysis.

Respond with a difficulty score (1-5) and a one-sentence reasoning for your rating."""


class DifficultyLabel(BaseModel):
    difficulty: int
    reasoning: str


def load_labels() -> dict:
    if LABELS_PATH.exists():
        return json.loads(LABELS_PATH.read_text())["labels"]
    return {}


def save_labels(labels: dict) -> None:
    LABELS_PATH.write_text(
        json.dumps({"model": JUDGE_MODEL, "rubric": RUBRIC, "labels": labels}, indent=2)
    )


def main():
    dataset = json.loads(DATASET_PATH.read_text())["questions"]
    labels = load_labels()
    client = Anthropic()

    remaining = [q for q in dataset if q["id"] not in labels]
    print(f"{len(labels)} already labeled, {len(remaining)} to go")

    for i, q in enumerate(remaining, 1):
        response = client.messages.parse(
            model=JUDGE_MODEL,
            max_tokens=2048,
            system=RUBRIC,
            messages=[{"role": "user", "content": f"Question: {q['prompt']}"}],
            output_format=DifficultyLabel,
        )
        label = response.parsed_output
        labels[q["id"]] = {"difficulty": label.difficulty, "reasoning": label.reasoning}
        save_labels(labels)
        print(f"[{i}/{len(remaining)}] {q['id']}: difficulty={label.difficulty}")

    print(f"Done. {len(labels)} labels written to {LABELS_PATH}")


if __name__ == "__main__":
    main()
