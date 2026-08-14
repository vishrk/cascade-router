import json


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid JSON body"})}

    prompt = body.get("prompt")
    if not prompt:
        return {"statusCode": 400, "body": json.dumps({"error": "missing 'prompt'"})}

    return {
        "statusCode": 200,
        "body": json.dumps({"response": "hardcoded response", "prompt": prompt}),
    }
