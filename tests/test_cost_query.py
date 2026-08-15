import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("ROUTING_LOGS_TABLE", "RoutingLogs")

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402


class TestCostQuery(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName="RoutingLogs",
            KeySchema=[{"AttributeName": "requestId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "requestId", "AttributeType": "S"},
                {"AttributeName": "date", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "DateIndex",
                    "KeySchema": [
                        {"AttributeName": "date", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )
        import cost_query

        cost_query._table = None
        self.cost_query = cost_query
        self.table = boto3.resource("dynamodb", region_name="us-east-1").Table("RoutingLogs")

    def tearDown(self):
        self.mock.stop()

    def _put(self, request_id, date, model, cost_usd):
        self.table.put_item(
            Item={
                "requestId": request_id,
                "date": date,
                "timestamp": f"{date}T00:00:00+00:00",
                "model": model,
                "costUsd": Decimal(str(cost_usd)),
            }
        )

    def test_query_since_and_aggregate(self):
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        self._put("r1", str(two_days_ago), "claude-haiku-4-5-20251001", 0.01)  # excluded, before --since
        self._put("r2", str(yesterday), "claude-haiku-4-5-20251001", 0.02)
        self._put("r3", str(today), "claude-opus-5", 0.10)

        items = self.cost_query.query_since(str(yesterday))
        self.assertEqual(len(items), 2)

        report = self.cost_query.aggregate(items)
        self.assertEqual(report["request_count"], 2)
        self.assertAlmostEqual(report["total_cost"], 0.12)
        self.assertAlmostEqual(report["by_model"]["claude-haiku-4-5-20251001"], 0.02)
        self.assertAlmostEqual(report["by_model"]["claude-opus-5"], 0.10)


if __name__ == "__main__":
    unittest.main()
