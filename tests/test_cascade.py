import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cascade import cascade_route  # noqa: E402


class FakeClient:
    """Queues responses in call order: first n calls are the cheap-model
    self-consistency samples, an optional final call is the escalation."""

    def __init__(self, texts):
        self._texts = iter(texts)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        text = next(self._texts)
        block = SimpleNamespace(type="text", text=text)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5)
        return SimpleNamespace(content=[block], usage=usage)


class TestCascade(unittest.TestCase):
    def test_high_confidence_stays_on_cheap_model(self):
        client = FakeClient(["Paris.", "Paris.", "Paris."])
        result = cascade_route(client, "capital of France?", "cheap-model", "expensive-model")

        self.assertEqual(result["model"], "cheap-model")
        self.assertFalse(result["escalated"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["response"], "Paris.")

    def test_low_confidence_escalates(self):
        client = FakeClient(["A", "B", "C", "expensive answer"])
        result = cascade_route(client, "hard question", "cheap-model", "expensive-model")

        self.assertEqual(result["model"], "expensive-model")
        self.assertTrue(result["escalated"])
        self.assertAlmostEqual(result["confidence"], 1 / 3)
        self.assertEqual(result["response"], "expensive answer")
        self.assertIn("escalated", result["reason"])

    def test_custom_threshold(self):
        # 2/3 agreement — escalates at threshold 0.9, stays cheap at 0.5
        client = FakeClient(["A", "A", "B", "expensive answer"])
        result = cascade_route(client, "q", "cheap-model", "expensive-model", confidence_threshold=0.9)
        self.assertTrue(result["escalated"])

        client = FakeClient(["A", "A", "B"])
        result = cascade_route(client, "q", "cheap-model", "expensive-model", confidence_threshold=0.5)
        self.assertFalse(result["escalated"])


if __name__ == "__main__":
    unittest.main()
