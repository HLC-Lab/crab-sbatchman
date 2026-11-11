"""Guards README.md and docs/*.md: size, links, install.sh flags, repo paths, placeholders, forbidden text.

Standard library and pytest only, no network. The flags come from the real `install.sh --help`.
"""

import re
import subprocess
from pathlib import Path

from forbidden import forbidden_or_skip

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DOCS = ROOT / "docs"

PAGES = ["install", "benchmarks", "campaigns", "launch", "results", "troubleshooting", "reference"]
PAGE_PATHS = [DOCS / f"{name}.md" for name in PAGES]
# The README fails above README_MAX_LINES; README_TARGET_LINES is the length the owner wants.
README_MAX_LINES = 60
README_TARGET_LINES = 40
PAGE_CAPS = {
    "install": 80,
    "benchmarks": 100,
    "campaigns": 100,
    "launch": 100,
    "results": 100,
    "troubleshooting": 300,
    "reference": 300,
}

# Words and phrases the prose never uses (whole words, any case). See "Writing docs" in the style guide.
BANNED_PHRASES = (
    "simply", "just", "easy", "easily", "please", "note that", "usually", "in order to",
    "above", "below", "the following", "this page", "it is recommended", "may", "should",
)  # fmt: skip
BANNED_PHRASE_RE = re.compile(
    r"\b(" + "|".join(p.replace(" ", r"\s+") for p in BANNED_PHRASES) + r")\b", re.IGNORECASE
)
# A list item that starts with bold text used as a label: `**Term:** x`, `**Term**: x`, `**Term** - x`.
BOLD_LEAD_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\*\*(?:[^*]+\*\*\s*[:\-]|[^*]*:\*\*)")

# The only <NAME> tokens the text may use. A later step adds a name here in the same commit as the
# text that needs it. Never a host, a user or an account.
ALLOWED_PLACEHOLDERS = {
    "<umbrella-url>",
    "<umbrella-dir>",
    "<YOUR_ACCOUNT>",
    "<login-host>",
    "<your-user>",
    "<benchmark>",
    "<job>",
    "<job-id>",
    "<cluster>",
    "<config>",
    "<tag>",
    "<timestamp>",
    "<laptop-dir>",
}

# Project names that are not decided yet. The personal words (account, user, host names) are in
# the untracked tests/forbidden-words.txt, see tests/forbidden.py.
FORBIDDEN = (
    "crab-suite",
    "net4exa",
)
FORBIDDEN_URL = re.compile(r"github\.com/HLC-Lab/(?!CRAB\b|crab-wrappers\b)")

# A token that starts with one of these must name a path of the checkout.
PATH_PREFIXES = ("benchmarks/", "docs/", "configs/", "tests/", "CRAB/", "crab-wrappers/")

# The top-level tracked names that the docs need not name.
TOP_LEVEL_SKIP = {"tests", ".gitignore", ".gitmodules", "README.md", "pytest.ini", "LICENSE", "CONTRIBUTING.md", ".github"}


def _allowed_missing_path(token: str) -> bool:
    """True for a path that is generated, untracked, or not created yet, so it may not exist."""
    # SbatchMan projects are created by `sbatchman init` on every machine and are git-ignored.
    if "SbatchMan/" in token:
        return True
    # Per-machine files: the site file made by install.sh, the git-ignored .local folder, env.sh.
    if token == "site/local.env" or token.startswith(".local/") or token == "env.sh":
        return True
    # The environment and the wrappers link inside CRAB/ are made by install.sh, not by the clone.
    if token.startswith("CRAB/.venv") or token == "CRAB/wrappers":
        return True
    # The template benchmark folder does not exist until a later step creates it.
    if token.startswith("benchmarks/_template"):
        return True
    return False


def _outside_fences(text: str) -> list[str]:
    """The lines of `text` that are not inside a ``` fence (the fence lines are dropped)."""
    lines = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            lines.append(line)
    return lines


def _inside_fences(text: str) -> list[str]:
    """The lines of `text` that are inside a ``` fence (the fence lines are dropped)."""
    lines = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            lines.append(line)
    return lines


def dash_problems(text: str) -> list[str]:
    """Lines with an em dash (U+2014) or an en dash (U+2013), code blocks included."""
    return [line for line in text.splitlines() if "—" in line or "–" in line]


def prose_problems(text: str) -> list[str]:
    """Banned words and phrases (lowercase) in the text outside fences, inline code and link targets."""
    prose = []
    for line in _outside_fences(text):
        line = re.sub(r"(`+).+?\1", " ", line)
        prose.append(re.sub(r"\]\([^)]*\)", "] ", line))
    found = BANNED_PHRASE_RE.findall("\n".join(prose))
    return [re.sub(r"\s+", " ", word.lower()) for word in found]


def bold_lead_problems(text: str) -> list[str]:
    """List items that start with bold text used as a label."""
    return [line for line in _outside_fences(text) if BOLD_LEAD_RE.match(line)]


def prompt_problems(text: str) -> list[str]:
    """Lines inside code fences that start with a `$ ` prompt."""
    return [line.strip() for line in _inside_fences(text) if line.lstrip().startswith("$ ")]


def heading_problems(text: str) -> list[str]:
    """Headings that end with a period or colon, or whose first character is a lowercase letter."""
    problems = []
    for line in _outside_fences(text):
        match = re.match(r"#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not match:
            continue
        heading = match.group(1)
        if heading.endswith((".", ":")):
            problems.append(f"{heading}: ends with a period or colon")
        if heading[:1].islower():
            problems.append(f"{heading}: does not start with an uppercase letter")
    return problems


def _slug(heading: str) -> str:
    """GitHub-style anchor: lowercase, punctuation dropped, spaces to hyphens."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _slugs(text: str) -> set[str]:
    """Every heading anchor of `text`, with GitHub's -1, -2 suffix for repeated headings."""
    seen: dict[str, int] = {}
    found = set()
    for line in _outside_fences(text):
        match = re.match(r"#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not match:
            continue
        slug = _slug(match.group(1))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        found.add(slug if count == 0 else f"{slug}-{count}")
    return found


def _h1_count(text: str) -> int:
    return sum(1 for line in _outside_fences(text) if re.match(r"# \S", line))


def _link_targets(text: str) -> list[str]:
    body = "\n".join(_outside_fences(text))
    return re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", body)


def link_problems(text: str, base: Path) -> list[str]:
    """Relative links of `text` (a file in folder `base`) that do not resolve, anchors included."""
    problems = []
    for target in _link_targets(text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path_part, _, anchor = target.partition("#")
        if path_part:
            resolved = (base / path_part).resolve()
            if not resolved.exists():
                problems.append(f"{target}: no such file")
                continue
        else:
            resolved = None
        if anchor:
            if resolved is not None and resolved.is_dir():
                problems.append(f"{target}: anchor on a folder")
                continue
            if resolved is not None and resolved.suffix == ".md":
                target_text = resolved.read_text()
            elif resolved is None:
                target_text = text
            else:
                continue
            if anchor not in _slugs(target_text):
                problems.append(f"{target}: no such heading")
    return problems


def install_flags() -> set[str]:
    help_text = subprocess.run(
        ["bash", "install.sh", "--help"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return set(re.findall(r"--[a-z][a-z-]*", help_text))


def flag_problems(text: str, flags: set[str]) -> list[str]:
    """Flags named on a line that mentions install.sh (in a fence or not) that it does not have."""
    problems = []
    for line in text.splitlines():
        if "install.sh" not in line:
            continue
        for flag in re.findall(r"--[a-z][a-z-]*", line):
            if flag not in flags:
                problems.append(f"{flag} in: {line.strip()}")
    return problems


def placeholder_problems(text: str) -> list[str]:
    """`<NAME>` tokens outside the allowed set (a heredoc marker `<<EOF` is not a token)."""
    found = re.findall(r"<[A-Za-z][\w-]*>", text)
    return [token for token in found if token not in ALLOWED_PLACEHOLDERS]


def _code_tokens(text: str) -> list[str]:
    """The whitespace-split words of every inline code span and every fenced line."""
    chunks = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if inside:
            chunks.append(line)
        else:
            chunks.extend(re.findall(r"`([^`]+)`", line))
    return [word for chunk in chunks for word in chunk.split()]


def path_problems(text: str) -> list[str]:
    """Code tokens that start like a repo path and name nothing that exists."""
    problems = []
    for word in _code_tokens(text):
        for match in re.finditer(r"(?<![\w./~-])((?:benchmarks|docs|configs|tests|CRAB|crab-wrappers)/[^\s`'\"),;:]*)", word):
            token = match.group(1).rstrip(".")
            if not token.startswith(PATH_PREFIXES):
                continue
            # A placeholder, a glob or an ellipsis stands for many paths: nothing to check.
            if "<" in token or "*" in token or "..." in token:
                continue
            if _allowed_missing_path(token):
                continue
            if not (ROOT / token).exists():
                problems.append(token)
    return problems


def _named_top_level(text: str) -> set[str]:
    """First path component of every inline code span (`./` dropped); fenced blocks are skipped."""
    names = set()
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    for span in re.findall(r"`([^`]+)`", text):
        for word in span.split():
            word = word.removeprefix("./")
            names.add(word.split("/", 1)[0])
    return names


def _all_docs() -> list[Path]:
    return [README, *PAGE_PATHS]


def _tracked_top_level() -> set[str]:
    listing = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return {line.split("/", 1)[0] for line in listing.splitlines() if line}


def test_readme_is_short_has_one_h1_and_links_every_page():
    text = README.read_text()
    lines = len(text.splitlines())
    assert lines <= README_MAX_LINES, f"{lines} lines, over {README_MAX_LINES} (target {README_TARGET_LINES})"
    assert _h1_count(text) == 1
    linked = {(ROOT / t.split("#", 1)[0]).resolve() for t in _link_targets(text)}
    for page in PAGE_PATHS:
        assert page.resolve() in linked, f"README does not link {page.name}"


def test_every_docs_page_exists_with_one_h1_and_a_size_cap():
    for page in PAGE_PATHS:
        assert page.is_file(), page.name
        text = page.read_text()
        assert _h1_count(text) == 1, page.name
        assert len(text.splitlines()) <= PAGE_CAPS[page.stem], page.name


def test_relative_links_resolve_and_anchors_match_a_heading():
    for path in _all_docs():
        assert link_problems(path.read_text(), path.parent) == [], path.name


def test_every_install_flag_named_in_the_docs_exists():
    flags = install_flags()
    assert {"--role", "--account", "--no-check", "--dry-run"} <= flags
    for path in _all_docs():
        assert flag_problems(path.read_text(), flags) == [], path.name


def test_repo_paths_in_code_exist():
    for path in _all_docs():
        assert path_problems(path.read_text()) == [], path.name


def test_only_allowed_placeholders():
    for path in _all_docs():
        assert placeholder_problems(path.read_text()) == [], path.name


def test_no_forbidden_project_word_or_url():
    for path in _all_docs():
        text = path.read_text()
        for word in FORBIDDEN:
            assert word not in text, f"{word} in {path.name}"
        assert not FORBIDDEN_URL.search(text), path.name


def test_no_personal_word():
    words = forbidden_or_skip()
    for path in _all_docs():
        text = path.read_text()
        for word in words:
            assert word not in text, f"{word!r} in {path.name}"


def test_every_top_level_tracked_path_is_named():
    named = set()
    for path in _all_docs():
        named |= _named_top_level(path.read_text())
    missing = sorted(_tracked_top_level() - TOP_LEVEL_SKIP - named)
    assert missing == []


def test_the_guards_catch_what_they_should(tmp_path):
    (tmp_path / "there.md").write_text("# There\n\n## Some Heading, here\n")
    bad = (
        "# Title\n"
        "Use <not-allowed> here and <<EOF.\n"
        "[gone](missing.md) and [bad anchor](there.md#nope) and [ok](there.md#some-heading-here)\n"
        "`./install.sh --bogus-flag`\n"
        "```\n./install.sh --role cluster --also-bogus\n```\n"
        "`docs/does-not-exist.md` and `benchmarks/_template/x` and `SbatchMan/x`\n"
    )
    assert placeholder_problems(bad) == ["<not-allowed>"]
    assert placeholder_problems("<umbrella-url> <<EOF") == []
    links = link_problems(bad, tmp_path)
    assert links == ["missing.md: no such file", "there.md#nope: no such heading"]
    flags = {"--role", "--account"}
    assert [p.split(" in:")[0] for p in flag_problems(bad, flags)] == ["--bogus-flag", "--also-bogus"]
    assert path_problems(bad) == ["docs/does-not-exist.md"]
    assert _slug("Some Heading, here") == "some-heading-here"
    assert _h1_count("# One\n```\n# not a heading\n```\n# Two\n") == 2


def test_no_em_or_en_dash():
    for path in _all_docs():
        assert dash_problems(path.read_text()) == [], path.name


def test_prose_has_no_filler_or_hedge_words():
    for path in _all_docs():
        assert prose_problems(path.read_text()) == [], path.name


def test_no_bold_lead_in_bullets():
    for path in _all_docs():
        assert bold_lead_problems(path.read_text()) == [], path.name


def test_no_shell_prompt_in_code_blocks():
    for path in _all_docs():
        assert prompt_problems(path.read_text()) == [], path.name


def test_headings_start_uppercase_and_do_not_end_with_a_period_or_colon():
    for path in _all_docs():
        assert heading_problems(path.read_text()) == [], path.name


def test_the_writing_rule_checks_catch_what_they_should():
    em, en = "—", "–"
    assert dash_problems(f"A pair {em} of words.\n```\nin {en} a block\n```\n") == [
        f"A pair {em} of words.",
        f"in {en} a block",
    ]
    assert dash_problems("A hyphen-ated word and a - dash.\n") == []

    bad_prose = (
        "Simply run it. Just run it. It is easy, easily done. Please wait.\n"
        "Note that you\n"
        "usually run it in order to see the output above and below.\n"
        "See the following list. This page says it is recommended that you may, or should.\n"
    )
    found = prose_problems(bad_prose)
    expected = [
        "simply", "just", "easy", "easily", "please", "note that", "usually", "in order to",
        "above", "below", "the following", "this page", "it is recommended", "may", "should",
    ]  # fmt: skip
    assert sorted(found) == sorted(expected)
    good_prose = (
        "Run `just build` and read `the following` and `may`.\n"
        "```\nsimply just should\n```\n"
        "The adjustment is mayhem-free: justice, easier and shoulder are other words.\n"
    )
    assert prose_problems(good_prose) == []

    bad_bold = (
        "- **Label:** text\n"
        "- **Label**: text\n"
        "  * **Label** - text\n"
        "1. **Label:** text\n"
    )
    assert len(bold_lead_problems(bad_bold)) == 4
    good_bold = (
        "- Open **Remotes** and press **+ Add cluster**.\n"
        "2. Press **Save** now.\n"
        "**Bold** at the start of a paragraph: fine.\n"
        "```\n- **Label:** text\n```\n"
    )
    assert bold_lead_problems(good_bold) == []

    bad_prompt = "```bash\n$ ./install.sh\n  $ source env.sh\n```\n"
    assert prompt_problems(bad_prompt) == ["$ ./install.sh", "$ source env.sh"]
    good_prompt = "Costs $ 5 outside.\n```bash\n./install.sh\necho $HOME\necho \"$ x\"\n```\n"
    assert prompt_problems(good_prompt) == []

    bad_headings = "# Title.\n## Ends with colon:\n### lowercase start\n#### Fine heading\n"
    assert heading_problems(bad_headings) == [
        "Title.: ends with a period or colon",
        "Ends with colon:: ends with a period or colon",
        "lowercase start: does not start with an uppercase letter",
    ]
    good_headings = '# Install\n## `crab web` fails\n### "wrappers/ is missing"\n```\n# comment.\n```\n'
    assert heading_problems(good_headings) == []


def test_the_page_caps_hold_and_never_loosen():
    assert README_MAX_LINES == 60 and README_TARGET_LINES == 40
    assert PAGE_CAPS == {
        "install": 80,
        "benchmarks": 100,
        "campaigns": 100,
        "launch": 100,
        "results": 100,
        "troubleshooting": 300,
        "reference": 300,
    }
    assert set(PAGE_CAPS) == set(PAGES)
