"""Small text helpers shared by the MCP service and API client."""

import re
import unicodedata

_RE_REASONING_BLOCK = re.compile(r"<reasoning>.*?</reasoning>\s*", re.DOTALL)
_RE_UNSAFE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: str) -> str:
    """Remove hidden reasoning and unsafe controls while preserving BSL text."""

    normalized = unicodedata.normalize("NFC", value or "")
    normalized = _RE_REASONING_BLOCK.sub("", normalized)
    return _RE_UNSAFE_CONTROL.sub("", normalized).strip()


def prepare_input(value: str, *, minimum: int, maximum: int, name: str) -> str:
    prepared = value.strip()
    if len(prepared) < minimum:
        raise ValueError(f"{name} must contain at least {minimum} characters")
    if len(prepared) > maximum:
        raise ValueError(f"{name} must not exceed {maximum} characters")
    return prepared
