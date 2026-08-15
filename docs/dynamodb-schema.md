# DynamoDB schema — routing logs

## Table: `RoutingLogs`

- **Partition key:** `requestId` (string, UUIDv4) — one item per routed request.
- No sort key: each request is a single, complete log item (score, features fired,
  model used, latency, cost stub, `model`, `date`, `timestamp`, ...).

## Why not `model_name` or `date` as the partition key

With only two model tiers, `model_name` as the partition key gives exactly two
partition values no matter how much traffic grows — every request routed to the
same tier lands on the same partition, capping write throughput at that one
partition's limit regardless of how much capacity the table has overall. `date`
has the same failure mode on a daily cycle: all of today's writes hash to one
key, so the busier the day, the hotter that single partition gets, while every
prior day's partition sits idle. `requestId` (a UUID) is high-cardinality and
unpredictable, so DynamoDB spreads writes evenly across partitions regardless
of traffic volume or shape.

## GSIs (for Phase 3 query patterns, not the write path)

- **`DateIndex`** — GSI PK `date` (`YYYY-MM-DD`), SK `timestamp`. Powers
  `cost_report.py --since <date>` range queries.
- **`ModelIndex`** — GSI PK `model`, SK `timestamp`. Powers cost-by-tier
  aggregation.

These reintroduce low-cardinality partition keys (`date`, `model`), but on the
*read* side, where it's an acceptable tradeoff for query simplicity at this
scale — not the write-critical base table.
`ponytail: date/model GSI PKs would hot-partition under heavy sustained
write/query volume; shard with a suffix (e.g. date#0-9) if that ever matters.`
