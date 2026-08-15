"""Fires N concurrent synthetic requests and checks whether the chosen
partition key (requestId) spreads evenly, versus the naive keys the schema
doc argues against (model_name, date).

DynamoDB doesn't expose actual physical partition placement via any API, so
this simulates partition assignment the same way DynamoDB does internally:
hash the key and bucket it. Run: python scripts/check_partition_distribution.py
"""

import datetime
import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("ROUTING_LOGS_TABLE", "RoutingLogs")

from moto import mock_aws  # noqa: E402

N = 2000
NUM_SIMULATED_PARTITIONS = 20
MAX_ACCEPTABLE_SKEW = 2.0  # no bucket should hold more than 2x the expected average


def bucket_for(key: str, num_buckets: int) -> int:
    digest = hashlib.md5(key.encode()).hexdigest()
    return int(digest, 16) % num_buckets


def fire_concurrent_requests(n: int) -> list[str]:
    import logger

    with ThreadPoolExecutor(max_workers=32) as pool:
        futures = [
            pool.submit(logger.log_request, f"synthetic prompt {i}", "claude-haiku-4-5-20251001", 0.1, {}, 10.0)
            for i in range(n)
        ]
        return [f.result() for f in futures]


def report(keys: list[str], num_buckets: int, label: str) -> float:
    counts = [0] * num_buckets
    for k in keys:
        counts[bucket_for(k, num_buckets)] += 1

    expected = len(keys) / num_buckets
    max_count = max(counts)
    skew = max_count / expected if expected else float("inf")
    print(f"{label}: max bucket = {max_count} items, expected ~{expected:.1f}, skew = {skew:.1f}x")
    return skew


def main():
    with mock_aws():
        import boto3

        boto3.client("dynamodb", region_name="us-east-1").create_table(
            TableName="RoutingLogs",
            KeySchema=[{"AttributeName": "requestId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "requestId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        request_ids = fire_concurrent_requests(N)

    assert len(set(request_ids)) == N, "concurrent writes produced colliding requestIds"
    print(f"Fired {N} concurrent requests, {len(set(request_ids))} unique requestIds\n")

    chosen_skew = report(request_ids, NUM_SIMULATED_PARTITIONS, "requestId (chosen key)     ")
    model_skew = report(["claude-haiku-4-5-20251001"] * N, NUM_SIMULATED_PARTITIONS, "model_name (naive key)     ")
    date_skew = report([datetime.date.today().isoformat()] * N, NUM_SIMULATED_PARTITIONS, "date (naive key)           ")

    print()
    assert chosen_skew <= MAX_ACCEPTABLE_SKEW, f"requestId distribution skewed {chosen_skew:.1f}x — investigate"
    assert model_skew > MAX_ACCEPTABLE_SKEW, "expected model_name to collapse onto one partition"
    assert date_skew > MAX_ACCEPTABLE_SKEW, "expected date to collapse onto one partition"
    print("PASS: requestId spreads evenly; naive keys (model_name, date) hot-partition as predicted.")


if __name__ == "__main__":
    main()
