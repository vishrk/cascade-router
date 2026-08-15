from confidence import self_consistency_confidence

CONFIDENCE_THRESHOLD = 0.67


def cascade_route(
    client,
    prompt: str,
    cheap_model: str,
    expensive_model: str,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    n: int = 3,
    cheap_max_tokens: int = 1024,
    expensive_max_tokens: int = 8192,
) -> dict:
    """Always try the cheap model first; escalate to the expensive model when
    its self-consistency confidence is below threshold. Returns the response
    plus which model answered, whether it escalated, and why."""
    signal = self_consistency_confidence(client, cheap_model, prompt, n=n, max_tokens=cheap_max_tokens)
    confidence = signal["confidence"]

    if confidence >= confidence_threshold:
        return {
            "model": cheap_model,
            "response": signal["representative"],
            "escalated": False,
            "confidence": confidence,
            "reason": f"cheap model confidence {confidence:.2f} >= threshold {confidence_threshold:.2f}",
        }

    reply = client.messages.create(
        model=expensive_model,
        max_tokens=expensive_max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in reply.content if block.type == "text")

    return {
        "model": expensive_model,
        "response": text,
        "escalated": True,
        "confidence": confidence,
        "reason": f"cheap model confidence {confidence:.2f} < threshold {confidence_threshold:.2f}, escalated",
    }
