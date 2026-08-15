import json
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv

from logger import log_request
from pricing import calculate_cost
from scorer import extract_features, score_from_features

load_dotenv()  # no-op in Lambda where there's no .env file; loads local secrets for dev

THRESHOLD = 0.5
CHEAP_MODEL = os.environ.get("CHEAP_MODEL", "claude-haiku-4-5-20251001")
EXPENSIVE_MODEL = os.environ.get("EXPENSIVE_MODEL", "claude-opus-5")
MAX_TOKENS = 4096
# Opus 5 runs adaptive thinking by default (no budget_tokens param anymore —
# that's removed on this model). Give it extra max_tokens headroom so
# thinking doesn't consume the whole budget before any text comes out (issue #3).
EXPENSIVE_MAX_TOKENS = 8192

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON body"})}

    prompt = body.get("prompt")
    if not prompt:
        return {"statusCode": 400, "body": json.dumps({"error": "missing 'prompt'"})}

    features = extract_features(prompt)
    complexity = score_from_features(features)
    model = EXPENSIVE_MODEL if complexity >= THRESHOLD else CHEAP_MODEL

    max_tokens = EXPENSIVE_MAX_TOKENS if model == EXPENSIVE_MODEL else MAX_TOKENS

    start = time.monotonic()
    reply = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = (time.monotonic() - start) * 1000

    text = "".join(block.text for block in reply.content if block.type == "text")

    cost_usd = calculate_cost(model, reply.usage.input_tokens, reply.usage.output_tokens)
    log_request(
        prompt,
        model,
        complexity,
        features,
        latency_ms,
        input_tokens=reply.usage.input_tokens,
        output_tokens=reply.usage.output_tokens,
        cost_usd=cost_usd,
    )

    if not text:
        return {
            "statusCode": 502,
            "body": json.dumps({"error": "model returned no text", "stop_reason": reply.stop_reason}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "response": text,
                "model": model,
                "score": complexity,
                "threshold": THRESHOLD,
            }
        ),
    }
