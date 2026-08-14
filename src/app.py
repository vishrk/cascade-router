import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from scorer import score

load_dotenv()  # no-op in Lambda where there's no .env file; loads local secrets for dev

THRESHOLD = 0.5
CHEAP_MODEL = os.environ.get("CHEAP_MODEL", "claude-haiku-4-5-20251001")
EXPENSIVE_MODEL = os.environ.get("EXPENSIVE_MODEL", "claude-opus-5")

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

    complexity = score(prompt)
    model = EXPENSIVE_MODEL if complexity >= THRESHOLD else CHEAP_MODEL

    reply = _get_client().messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in reply.content if block.type == "text")

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
