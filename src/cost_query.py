import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["ROUTING_LOGS_TABLE"])
    return _table


def query_since(since_date: str) -> list[dict]:
    """Fetch every log item with date >= since_date via DateIndex (one Query per day)."""
    table = _get_table()
    day = datetime.strptime(since_date, "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()

    items = []
    while day <= today:
        kwargs = {"IndexName": "DateIndex", "KeyConditionExpression": Key("date").eq(day.isoformat())}
        while True:
            resp = table.query(**kwargs)
            items.extend(resp["Items"])
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        day += timedelta(days=1)

    return items


def aggregate(items: list[dict]) -> dict:
    by_model: dict[str, float] = {}
    for item in items:
        by_model[item["model"]] = by_model.get(item["model"], 0.0) + float(item["costUsd"])

    return {
        "request_count": len(items),
        "total_cost": sum(by_model.values()),
        "by_model": by_model,
    }
