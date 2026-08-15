import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from confidence import self_consistency_confidence  # noqa: E402


class FakeClient:
    def __init__(self, texts):
        self._texts = iter(texts)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        text = next(self._texts)
        block = SimpleNamespace(type="text", text=text)
        return SimpleNamespace(content=[block])


class TestConfidence(unittest.TestCase):
    def test_unanimous_agreement_is_full_confidence(self):
        client = FakeClient(["Paris.", "Paris.", "Paris."])
        result = self_consistency_confidence(client, "model", "capital of France?", n=3)
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["representative"], "Paris.")

    def test_case_and_whitespace_are_normalized(self):
        client = FakeClient(["  Paris.  ", "PARIS.", "paris."])
        result = self_consistency_confidence(client, "model", "capital of France?", n=3)
        self.assertEqual(result["confidence"], 1.0)

    def test_disagreement_lowers_confidence(self):
        client = FakeClient(["Paris.", "Lyon.", "Marseille."])
        result = self_consistency_confidence(client, "model", "capital of France?", n=3)
        self.assertAlmostEqual(result["confidence"], 1 / 3)

    def test_majority_wins(self):
        client = FakeClient(["Paris.", "Paris.", "Lyon."])
        result = self_consistency_confidence(client, "model", "capital of France?", n=3)
        self.assertAlmostEqual(result["confidence"], 2 / 3)
        self.assertEqual(result["representative"], "Paris.")


if __name__ == "__main__":
    unittest.main()
