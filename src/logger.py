import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["ROUTING_LOGS_TABLE"])
    return _table


def log_request(prompt: str, model: str, score: float, features: dict, latency_ms: float, cost_usd: float = 0.0) -> str:
    """Write one routing decision to RoutingLogs. Returns the generated requestId."""
    now = datetime.now(timezone.utc)
    request_id = str(uuid.uuid4())

    _get_table().put_item(
        Item={
            "requestId": request_id,
            "date": now.strftime("%Y-%m-%d"),
            "timestamp": now.isoformat(),
            "model": model,
            "score": Decimal(str(score)),
            "features": features,
            "latencyMs": Decimal(str(latency_ms)),
            "costUsd": Decimal(str(cost_usd)),
            "prompt": prompt,
        }
    )
    return request_id
