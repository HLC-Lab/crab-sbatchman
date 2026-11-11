"""The words no tracked file may contain, read from the untracked tests/forbidden-words.txt.

One word per line; blank lines and lines starting with # are ignored. The file is git-ignored on
purpose: the words are personal data (account, user and host names), so the list is never
committed. Without the file the tests that need it skip.
"""

from pathlib import Path

import pytest

WORDS_FILE = Path(__file__).resolve().parent / "forbidden-words.txt"


def load_forbidden() -> list[str]:
    """The forbidden words, or [] when tests/forbidden-words.txt is not there."""
    try:
        lines = WORDS_FILE.read_text().splitlines()
    except OSError:
        return []
    words = [line.strip() for line in lines]
    return [word for word in words if word and not word.startswith("#")]


def forbidden_or_skip() -> list[str]:
    """load_forbidden(), but skips the calling test when there is no list to check against."""
    words = load_forbidden()
    if not words:
        pytest.skip("tests/forbidden-words.txt is not present")
    return words
