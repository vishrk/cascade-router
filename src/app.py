import json


def handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "cascade-router: no-op"}),
    }
