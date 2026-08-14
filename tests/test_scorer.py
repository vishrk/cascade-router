import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scorer import extract_features, score  # noqa: E402


class TestScorer(unittest.TestCase):
    def test_obvious_easy(self):
        prompt = "What is the capital of France?"
        features = extract_features(prompt)
        self.assertTrue(features["has_easy_keywords"])
        self.assertFalse(features["has_code"])
        self.assertFalse(features["has_math"])
        self.assertLess(score(prompt), 0.3)

    def test_obvious_hard(self):
        prompt = (
            "Design and optimize this function, then prove its correctness "
            "and explain why it beats the naive approach:\n"
            "```python\ndef foo(x):\n    return x ** 2\n```"
        )
        features = extract_features(prompt)
        self.assertTrue(features["has_code"])
        self.assertTrue(features["has_hard_keywords"])
        self.assertGreater(score(prompt), 0.6)

    def test_ambiguous(self):
        prompt = "Tell me about how photosynthesis works in plants."
        features = extract_features(prompt)
        self.assertFalse(features["has_code"])
        self.assertFalse(features["has_hard_keywords"])
        self.assertFalse(features["has_easy_keywords"])
        s = score(prompt)
        self.assertGreater(s, 0.0)
        self.assertLess(s, 0.5)

    def test_easy_scores_lower_than_hard(self):
        easy = score("What is 2 + 2?")
        hard = score(
            "Derive and prove the time complexity trade-offs of this algorithm:\n"
            "```python\ndef f(n): return f(n-1) + f(n-2)\n```"
        )
        self.assertLess(easy, hard)


if __name__ == "__main__":
    unittest.main()
