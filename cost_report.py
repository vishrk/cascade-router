#!/usr/bin/env python3
"""Print measured spend since a given date. Run: python cost_report.py --since 2026-08-01"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv  # noqa: E402

from cost_query import aggregate, query_since  # noqa: E402

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    items = query_since(args.since)
    report = aggregate(items)

    print(f"Requests: {report['request_count']}")
    print(f"Total spend: ${report['total_cost']:.6f}")
    print("By model:")
    for model, cost in sorted(report["by_model"].items(), key=lambda kv: -kv[1]):
        print(f"  {model}: ${cost:.6f}")


if __name__ == "__main__":
    main()
