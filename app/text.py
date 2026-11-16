from __future__ import annotations

import re


_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese text into words, characters, and bigrams."""
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text.lower()):
        value = match.group(0)
        if re.fullmatch(r"[a-z0-9]+", value):
            tokens.append(value)
            continue

        tokens.extend(value)
        tokens.extend(value[index : index + 2] for index in range(len(value) - 1))
        if len(value) > 2:
            tokens.append(value)
    return tokens

