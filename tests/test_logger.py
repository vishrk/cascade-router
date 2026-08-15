import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("ROUTING_LOGS_TABLE", "RoutingLogs")

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName="RoutingLogs",
            KeySchema=[{"AttributeName": "requestId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "requestId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        import logger

        logger._table = None  # reset cached table handle between tests
        self.logger = logger

    def tearDown(self):
        self.mock.stop()

    def test_log_request_writes_expected_item(self):
        features = {"token_count": 5, "has_code": False, "has_math": False}
        request_id = self.logger.log_request(
            prompt="What is 2 + 2?",
            model="claude-haiku-4-5-20251001",
            score=0.1,
            features=features,
            latency_ms=123.4,
            input_tokens=42,
            output_tokens=8,
            cost_usd=0.002,
        )

        table = boto3.resource("dynamodb", region_name="us-east-1").Table("RoutingLogs")
        item = table.get_item(Key={"requestId": request_id})["Item"]

        self.assertEqual(item["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(item["prompt"], "What is 2 + 2?")
        self.assertEqual(float(item["score"]), 0.1)
        self.assertEqual(float(item["latencyMs"]), 123.4)
        self.assertEqual(item["inputTokens"], 42)
        self.assertEqual(item["outputTokens"], 8)
        self.assertEqual(float(item["costUsd"]), 0.002)
        self.assertEqual(item["features"], features)
        self.assertIn("date", item)
        self.assertIn("timestamp", item)

    def test_log_request_returns_unique_ids(self):
        id1 = self.logger.log_request("a", "m", 0.0, {}, 1.0)
        id2 = self.logger.log_request("b", "m", 0.0, {}, 1.0)
        self.assertNotEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
