def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def self_consistency_confidence(client, model: str, prompt: str, n: int = 3, max_tokens: int = 1024) -> dict:
    """Sample the cheap model n times and score confidence by sample agreement.

    Crude but cheap: confidence is the fraction of samples whose normalized
    text matches the most common one. Anthropic doesn't expose logprobs, so
    this is the practical alternative for a confidence signal.
    """
    texts = []
    usage = []
    for _ in range(n):
        reply = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=1.0,
            messages=[{"role": "user", "content": prompt}],
        )
        texts.append("".join(block.text for block in reply.content if block.type == "text"))
        usage.append((reply.usage.input_tokens, reply.usage.output_tokens))

    normalized = [_normalize(t) for t in texts]
    counts = {}
    for norm in normalized:
        counts[norm] = counts.get(norm, 0) + 1
    majority_norm, majority_count = max(counts.items(), key=lambda kv: kv[1])
    representative = next(t for t, norm in zip(texts, normalized) if norm == majority_norm)

    return {
        "confidence": majority_count / n,
        "representative": representative,
        "responses": texts,
        "usage": usage,
    }
