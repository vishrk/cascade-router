import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pricing import calculate_cost  # noqa: E402


class TestPricing(unittest.TestCase):
    def test_known_model(self):
        cost = calculate_cost("claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertAlmostEqual(cost, 1.00 + 5.00)

    def test_unknown_model_returns_zero(self):
        self.assertEqual(calculate_cost("some-unlisted-model", 1000, 1000), 0.0)

    def test_zero_tokens_is_free(self):
        self.assertEqual(calculate_cost("claude-opus-5", 0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
