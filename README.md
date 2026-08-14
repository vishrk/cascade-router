# Cascade Router

A complexity-based LLM router: a Lambda service that scores incoming prompts
for difficulty and routes each one to the cheapest model tier likely to
answer it correctly, escalating to a stronger model when needed. Built as a
phased project — starting from a simple heuristic scorer, moving through a
trained classifier, and ending with a confidence-based cascade — with an eval
harness that plots accuracy-vs-cost to justify each routing decision with data
rather than intuition.
