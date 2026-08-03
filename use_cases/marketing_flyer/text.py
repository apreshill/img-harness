"""Marketing exact-text compare (no provider I/O — extract uses openai.responses in schema)."""

from __future__ import annotations


def compare_required(extracted: list[str], required_text: list) -> dict:
    required = {str(v) for v in required_text}
    got = set(extracted)
    missing = sorted(required - got)
    extra = sorted(got - required)
    return {
        'pass': not missing and not extra,
        'missing': missing,
        'extra': extra,
    }
