# Cascade Router

A complexity-based LLM router: a Lambda service that scores incoming prompts
for difficulty and routes each one to the cheapest model tier likely to
answer it correctly, escalating to a stronger model when needed. Built as a
phased project — starting from a simple heuristic scorer, moving through a
trained classifier, and ending with a confidence-based cascade — with an eval
harness that plots accuracy-vs-cost to justify each routing decision with data
rather than intuition.

**Status:** Phase 0 complete — SAM stack scaffolded, no-op Lambda deploys
behind API Gateway. Phase 1 (heuristic router) is next.

## Architecture (target end state)

- **Entry point:** API Gateway → Lambda (Python)
- **Router:** starts as heuristic (Phase 1), evolves into a trained classifier
  (Phase 5), then a cascade with confidence-based escalation (Phase 6)
- **Storage:** DynamoDB — request/routing/cost logs, designed around a
  partition key that avoids hot partitions at scale (not `model_name` or
  `date` alone)
- **Eval:** a small labeled eval set + harness that plots an accuracy-vs-cost
  Pareto curve, used to justify routing thresholds with actual data
- **Two model tiers:** one cheap/fast model, one expensive/strong model

## Getting started

```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY
sam build
sam deploy --guided
```

Prod secrets live in SSM Parameter Store, not env vars — see the comment in
`.env.example`.

## Roadmap

| Phase | Scope | Definition of done |
|---|---|---|
| 0 | Scaffolding — IaC stack, config management, least-privilege IAM | `sam deploy` succeeds with an empty/no-op Lambda |
| 1 | Baseline heuristic router — regex/token-count scorer, routes to one of two real models | Deployed endpoint routes real requests based on a heuristic score and explains why |
| 2 | DynamoDB logging, designed against hot partitions | Every routed request is logged with an explainable trail; a script proves the partition key holds up under concurrent load |
| 3 | Cost tracking — real tokenizers, pricing table, cost reports | `python cost_report.py --since <date>` prints real measured spend by tier |
| 4 | Eval harness + labeled dataset | A plotted accuracy-vs-cost Pareto curve backs the threshold choice |
| 5 | Trained classifier router (v2), selectable via feature flag alongside v1 | Side-by-side chart showing v2 vs v1 at equivalent cost |
| 6 | Cascade routing — cheap model first, escalate on low confidence | Three comparable Pareto curves (heuristic / classifier / cascade) with a tradeoffs write-up |
| 7 | Observability & polish — structured logs, CloudWatch dashboard, README rewrite | A stranger can clone the repo and understand the system from the README alone |
| 8 | Stretch — adaptive threshold recalibration, shadow routing | — |

## Building this with Claude Code

This project is built one task at a time, each sized to a single commit:

1. Say "Let's start Phase N, task M. Implement just this task, then stop and
   show me the diff before committing."
2. Review the diff, then say "commit this."
3. Repeat for the next task. Tasks are never combined "for efficiency" — the
   small-commit history is itself a deliverable.
4. At the end of each phase, check its Definition of done explicitly before
   moving on.

### Commit conventions

- `feat(router): ...`, `feat(eval): ...`, `fix(dynamo): ...`,
  `test(router): ...`, `docs(schema): ...`, `chore(infra): ...`
- One task = one commit. Splitting a task further (e.g. tests separate from
  the function they test) is fine — smaller is better, not worse.
- Commit messages should be specific enough that the log alone tells the
  story of the build, phase by phase.
