"""Guards README.md and docs/*.md: size, links, install.sh flags, repo paths, placeholders, forbidden text.

Standard library, PyYAML and pytest only, no network. The flags come from the real `install.sh --help`.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from forbidden import forbidden_or_skip

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DOCS = ROOT / "docs"

PAGES = ["index", "install", "connect", "benchmarks", "campaigns", "launch", "results", "troubleshooting", "reference", "presets", "plots", "glossary"]
PAGE_PATHS = [DOCS / f"{name}.md" for name in PAGES]
# The README fails above README_MAX_LINES; README_TARGET_LINES is the length the owner wants.
README_MAX_LINES = 60
README_TARGET_LINES = 40
PAGE_CAPS = {
    "index": 40,
    "install": 80,
    "connect": 70,
    "benchmarks": 110,
    "campaigns": 120,
    "launch": 100,
    "results": 100,
    "troubleshooting": 300,
    "reference": 300,
    "presets": 120,
    "plots": 120,
    "glossary": 60,
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
FORBIDDEN_URL = re.compile(r"github\.com/HLC-Lab/(?!CRAB\b|crab-wrappers\b|crab-sbatchman\b)")
# The umbrella's own address, in the form of the submodule URLs of `.gitmodules`.
UMBRELLA_CLONE_URL = "https://github.com/HLC-Lab/crab-sbatchman.git"
# Text that marks a page as unfinished.
LEFTOVER_RE = re.compile(r"<umbrella-url>|working\s+title|\bTODO\b", re.IGNORECASE)

# A token that starts with one of these must name a path of the checkout.
PATH_PREFIXES = ("benchmarks/", "docs/", "configs/", "tests/", "CRAB/", "crab-wrappers/")

# The top-level tracked names that the docs need not name.
TOP_LEVEL_SKIP = {"tests", ".gitignore", ".gitmodules", "README.md", "pytest.ini", "LICENSE", "CONTRIBUTING.md", "RELEASING.md", ".github"}


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
    # CRAB's git-ignored per-machine folder: private wrappers and their samples, receipts.
    if token.startswith("CRAB/local/"):
        return True
    # The dashboard creates the staging folder when it writes a campaign file.
    if token.startswith("CRAB/.web_staging"):
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


def undocumented_flags(reference: str, flags: set[str]) -> list[str]:
    """The `install.sh` flags (sorted) that the text of the reference page never names."""
    return sorted(flag for flag in flags if flag not in reference)


def placeholder_problems(text: str) -> list[str]:
    """`<NAME>` tokens outside the allowed set (a heredoc marker `<<EOF` is not a token)."""
    found = re.findall(r"<[A-Za-z][\w-]*>", text)
    return [token for token in found if token not in ALLOWED_PLACEHOLDERS]


def leftover_problems(text: str) -> list[str]:
    """Placeholders for the umbrella address, the words "working title" and TODO markers (as written)."""
    return [match.group(0) for match in LEFTOVER_RE.finditer(text)]


def clone_url_problems(text: str) -> list[str]:
    """`git clone` command lines (in code fences) that do not clone the umbrella from its address."""
    return [
        line.strip()
        for line in _inside_fences(text)
        if "git clone" in line and UMBRELLA_CLONE_URL not in line.split()
    ]


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


def test_the_update_section_tells_a_laptop_to_keep_its_role():
    # A bare ./install.sh runs the cluster role: on a laptop it asks for a Slurm account.
    install = (DOCS / "install.md").read_text()
    update = install.split("\n## Update", 1)[1]
    assert "./install.sh --role laptop" in update


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


def test_the_connect_page_names_the_sbatchman_config_folder_of_each_system():
    # SbatchMan builds the folder with platformdirs: it differs on macOS. Connect owns the folder paths.
    connect = (DOCS / "connect.md").read_text()
    assert "~/.config/sbatchman/" in connect
    assert "~/Library/Application Support/sbatchman/" in connect


def test_relative_links_resolve_and_anchors_match_a_heading():
    for path in _all_docs():
        assert link_problems(path.read_text(), path.parent) == [], path.name


def test_every_install_flag_named_in_the_docs_exists():
    flags = install_flags()
    assert {"--role", "--account", "--no-check", "--dry-run"} <= flags
    for path in _all_docs():
        assert flag_problems(path.read_text(), flags) == [], path.name


def test_contributing_lists_the_tokens_that_install_sh_fills():
    # A configs template with any other <TOKEN> makes install.sh stop on "unfilled tokens".
    script = (ROOT / "install.sh").read_text()
    tokens = set(re.findall(r"token_\w+='(<[A-Z_]+>)'", script))
    assert len(tokens) == 4, tokens
    contributing = (ROOT / "CONTRIBUTING.md").read_text()
    section = contributing.split("## Add a configs file", 1)[1].split("\n## ", 1)[0]
    assert set(re.findall(r"<[A-Z_]+>", section)) == tokens


def test_the_reference_page_documents_every_install_flag():
    flags = install_flags()
    assert undocumented_flags((DOCS / "reference.md").read_text(), flags) == []


def test_repo_paths_in_code_exist():
    for path in _all_docs():
        assert path_problems(path.read_text()) == [], path.name


CRAB_BLOB_RE = re.compile(r"^https://github\.com/HLC-Lab/CRAB/blob/([^/]+)/([^#]+)(?:#(.+))?$")
SUBMODULE_LINK_RE = re.compile(r"^(?:\.\.?/)*(?:CRAB|crab-wrappers)/")


def test_docs_link_into_the_submodules_by_absolute_url_not_by_path():
    # github.com serves no folder below a submodule of this repository: such a link is a 404 there.
    for path in _all_docs():
        bad = [t for t in _link_targets(path.read_text()) if SUBMODULE_LINK_RE.match(t)]
        assert bad == [], f"{path.name}: {bad}"


def test_absolute_crab_links_name_a_file_and_heading_of_the_pinned_checkout():
    crab = ROOT / "CRAB"
    if not (crab / "Makefile").exists():
        pytest.skip("the CRAB submodule is not checked out")
    described = subprocess.run(
        ["git", "-C", str(crab), "describe", "--tags", "--exact-match"], capture_output=True, text=True
    )
    pinned_tag = described.stdout.strip() if described.returncode == 0 else None
    seen = 0
    for path in _all_docs():
        for target in _link_targets(path.read_text()):
            match = CRAB_BLOB_RE.match(target)
            if not match:
                continue
            seen += 1
            tag, rel, anchor = match.groups()
            if pinned_tag is not None:
                assert tag == pinned_tag, f"{path.name}: {target} is not the pinned tag {pinned_tag}"
            assert (crab / rel).is_file(), f"{path.name}: {target}: no such file in CRAB"
            if anchor:
                assert anchor in _slugs((crab / rel).read_text()), f"{path.name}: {target}: no such heading"
    assert seen >= 2


def test_only_allowed_placeholders():
    for path in _all_docs():
        assert placeholder_problems(path.read_text()) == [], path.name


def test_no_forbidden_project_word_or_url():
    for path in _all_docs():
        text = path.read_text()
        for word in FORBIDDEN:
            assert word not in text, f"{word} in {path.name}"
        assert not FORBIDDEN_URL.search(text), path.name


def test_the_add_cluster_example_checks_the_host_key_and_uses_the_form_labels():
    connect = (DOCS / "connect.md").read_text()
    assert "| Host key | strict" in connect
    assert "| Host key | insecure" not in connect
    assert "| Auth | agent (ssh-agent / cert) |" in connect
    # The one place that tells when `insecure` is acceptable also warns about `password`.
    limits = (DOCS / "reference.md").read_text().split("## Known limits", 1)[1]
    assert "`insecure`" in limits and "`password`" in limits


def test_no_unfinished_marker_in_any_page():
    for path in _all_docs():
        assert leftover_problems(path.read_text()) == [], path.name


def test_the_readme_clones_the_umbrella_from_its_address():
    assert re.fullmatch(r"https://github\.com/HLC-Lab/[\w-]+\.git", UMBRELLA_CLONE_URL)
    readme = README.read_text()
    assert f"git clone --recurse-submodules {UMBRELLA_CLONE_URL}\n" in readme
    for path in _all_docs():
        assert clone_url_problems(path.read_text()) == [], path.name


OPTIONAL_RE = re.compile(r"\boptional\b", re.IGNORECASE)


def test_the_laptop_is_not_called_optional():
    # The dashboard, `sbatchman fetch` and `sbatchman visualize` all run on the laptop.
    for path in _all_docs():
        text = path.read_text()
        assert "Optional: install the umbrella on your laptop" not in text, path.name
        for line in text.splitlines():
            assert not (OPTIONAL_RE.search(line) and "laptop" in line.lower()), f"{path.name}: {line}"
    install = (DOCS / "install.md").read_text()
    assert "\n## Install on your laptop\n" in install
    assert "The laptop is part of the setup" in install
    needs = (DOCS / "index.md").read_text().split("## What you need", 1)[1].split("\n## ", 1)[0]
    assert "laptop" in needs


def test_readme_does_not_repeat_the_install_steps():
    # The install steps live in docs/install.md only; the README holds the clone line and points there.
    readme = README.read_text()
    assert "./install.sh" not in readme
    assert len(re.findall(r"^\s*```bash\s*$", readme, flags=re.MULTILINE)) <= 1
    linked = {(ROOT / t.split("#", 1)[0]).resolve() for t in _link_targets(readme)}
    assert (DOCS / "install.md").resolve() in linked


def test_no_personal_word():
    words = forbidden_or_skip()
    for path in _all_docs():
        text = path.read_text()
        for word in words:
            assert word not in text, f"{word!r} in {path.name}"


def test_the_connect_step_says_to_run_crab_web_on_the_laptop():
    # Any other user of a shared machine can read the dashboard token over loopback.
    connect = (DOCS / "connect.md").read_text()
    step = connect.split("## Add the cluster in crab web", 1)[1].split("2. Open", 1)[0]
    assert "on your laptop" in step and "not on the cluster" in step


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
    assert placeholder_problems("<umbrella-url> <umbrella-dir> <<EOF") == ["<umbrella-url>"]
    assert leftover_problems("Clone <umbrella-url>. A Working  Title. TODO: x. todo\n") == [
        "<umbrella-url>",
        "Working  Title",
        "TODO",
        "todo",
    ]
    assert leftover_problems("Run `todoist` and `<umbrella-dir>`.\n") == []
    good_clone = f"```bash\ngit clone --recurse-submodules {UMBRELLA_CLONE_URL}\n```\nPlain `git clone` in prose.\n"
    assert clone_url_problems(good_clone) == []
    bad_clone = (
        "```bash\n"
        "git clone --recurse-submodules <umbrella-url> <umbrella-dir>\n"
        "git clone https://github.com/HLC-Lab/crab-sbatchman\n"
        "git clone https://github.com/HLC-Lab/crab-wrappers.git\n"
        "```\n"
    )
    assert len(clone_url_problems(bad_clone)) == 3
    assert FORBIDDEN_URL.search("github.com/HLC-Lab/crab-sbatchman.git") is None
    assert FORBIDDEN_URL.search("github.com/HLC-Lab/other") is not None
    links = link_problems(bad, tmp_path)
    assert links == ["missing.md: no such file", "there.md#nope: no such heading"]
    flags = {"--role", "--account"}
    assert [p.split(" in:")[0] for p in flag_problems(bad, flags)] == ["--bogus-flag", "--also-bogus"]
    assert path_problems(bad) == ["docs/does-not-exist.md"]
    assert undocumented_flags("`--role` and `--dry-run`", {"--role", "--dry-run", "--offline"}) == ["--offline"]
    assert _slug("Some Heading, here") == "some-heading-here"
    assert _h1_count("# One\n```\n# not a heading\n```\n# Two\n") == 2


def test_the_reference_says_crab_update_stops_in_the_umbrella():
    # CRAB 1.5.0 refuses inside a superproject; it does not move CRAB off the pin.
    limits = (DOCS / "reference.md").read_text().split("## Known limits", 1)[1]
    assert "crab update" in limits
    assert "moves CRAB off the pinned commit" not in limits
    assert "stops" in limits


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
        "index": 40,
        "install": 80,
        "connect": 70,
        "benchmarks": 110,
        "campaigns": 120,
        "launch": 100,
        "results": 100,
        "troubleshooting": 300,
        "reference": 300,
        "presets": 120,
        "plots": 120,
        "glossary": 60,
    }
    assert set(PAGE_CAPS) == set(PAGES)


def test_releasing_names_the_pin_chain_and_stays_short():
    path = ROOT / "RELEASING.md"
    assert path.is_file()
    text = path.read_text()
    assert len(text.splitlines()) <= 45
    for needle in ("+sbatchman", "crab-wrappers", "tests/pins.py", "git submodule"):
        assert needle in text, needle
    # The maintainer's private tooling is never named in a public file.
    assert ".crab-web-dev" not in text and ".claude" not in text


def test_contributing_points_to_releasing_for_the_pin():
    assert "RELEASING.md" in (ROOT / "CONTRIBUTING.md").read_text()


MAINTAINER_DOCS = [ROOT / "CONTRIBUTING.md", ROOT / "RELEASING.md"]


def test_the_maintainer_docs_follow_the_writing_rules():
    for path in MAINTAINER_DOCS:
        text = path.read_text()
        assert dash_problems(text) == [], path.name
        assert prose_problems(text) == [], path.name
        assert bold_lead_problems(text) == [], path.name
        assert prompt_problems(text) == [], path.name
        assert heading_problems(text) == [], path.name
        assert link_problems(text, path.parent) == [], path.name
        assert _h1_count(text) == 1, path.name
        assert leftover_problems(text) == [], path.name


def test_the_maintainer_docs_name_no_personal_word_or_forbidden_project_word():
    words = forbidden_or_skip()
    for path in MAINTAINER_DOCS:
        text = path.read_text()
        for word in (*words, *FORBIDDEN):
            assert word not in text, f"{word!r} in {path.name}"
        assert not FORBIDDEN_URL.search(text), path.name


def test_the_run_page_registers_the_supported_benchmark_itself():
    # A newcomer runs Blink from launch.md alone: the register step lives there, not in benchmarks.md.
    launch = (DOCS / "launch.md").read_text()
    assert launch.splitlines()[0] == "# Run a benchmark"
    assert "## Register Blink" in launch
    assert "crab setup" in _inside_fences(launch)
    assert "Install or configure a supported benchmark" in launch
    benchmarks = (DOCS / "benchmarks.md").read_text()
    assert "## Register a supported benchmark" not in benchmarks
    assert "Install or configure a supported benchmark" not in benchmarks
    assert "launch.md#register-blink" in benchmarks
    # The wizard asks for a strategy by number, and Enter picks 1 (auto-detect): the page names the option for Blink.
    assert 'type `4` for "Download and compile from source layout"' in launch
    assert "Enter picks `1`" in launch


LEONARDO_MODULE_LINE = "module load gcc/12.2.0 openmpi/4.1.6--gcc--12.2.0-cuda-12.2 cuda/12.2 cmake/3.27.9"


def test_the_run_page_gives_the_leonardo_module_line_of_the_crab_docs():
    launch = (DOCS / "launch.md").read_text()
    # A step indents its fence, so compare the lines without their indentation.
    assert LEONARDO_MODULE_LINE in [line.strip() for line in _inside_fences(launch)]
    crab_doc = ROOT / "CRAB" / "docs" / "reference" / "supported-benchmarks.md"
    if not crab_doc.is_file():
        pytest.skip("the CRAB submodule is not checked out")
    assert LEONARDO_MODULE_LINE in crab_doc.read_text()
    # The CPU config of the configs file loads the same compiler and MPI.
    configs = (ROOT / "configs" / "leonardo.yaml").read_text()
    assert '"gcc/12.2.0"' in configs and '"openmpi/4.1.6--gcc--12.2.0-cuda-12.2"' in configs


def test_the_pin_check_allows_only_the_module_line_of_the_run_page(tmp_path):
    # Module specs look like versions to tests/pins.py. Only that exact line is allowed, nothing near it.
    import pins

    # pins.check reads the pins from the CRAB checkout, which the CI job without submodules does not have.
    if not (ROOT / "CRAB" / "src").is_dir():
        pytest.skip("needs the CRAB checkout")
    docs_copy = tmp_path / "docs"
    shutil.copytree(DOCS, docs_copy)
    assert [p for p in pins.check(docs_copy) if p.startswith("launch.md")] == []
    launch = docs_copy / "launch.md"
    text = launch.read_text()
    launch.write_text(text + "\nBuilt with gcc/12.2.0 and tag 9.9.9.\n" + LEONARDO_MODULE_LINE.replace("12.2.0", "11.1.0", 1) + "\n")
    found = [p for p in pins.check(docs_copy) if p.startswith("launch.md")]
    assert any(" 12.2.0 " in p for p in found), found
    assert any(" 9.9.9 " in p for p in found), found
    assert any(" 11.1.0 " in p for p in found), found


def test_results_adds_fetch_dirs_to_the_saved_block():
    # Connect saved the cluster block: Results adds fetch_dirs lines to it and shows the final file once.
    results = (DOCS / "results.md").read_text()
    assert "fetch_dirs" in results
    # Exactly one `[[clusters]]` in the page, and it sits in the complete example.
    assert results.count("[[clusters]]") == 1
    # A step may indent the fence, so compare the lines without their indentation.
    blocks = re.findall(r"^\s*```toml\n(.*?)^\s*```", results, flags=re.DOTALL | re.MULTILINE)
    example = [line.strip() for line in next(block for block in blocks if "[[clusters]]" in block).splitlines()]
    assert example.count("[[clusters]]") == 1
    assert example.count("[global]") == 1
    assert "[[clusters.fetch_dirs]]" in example
    # Every line of the cluster block that Connect saves (name, host, port, user) is in the example.
    connect = (DOCS / "connect.md").read_text()
    saved = re.search(r"```toml\n(\[\[clusters\]\]\n.*?)```", connect, flags=re.DOTALL)
    assert saved, "connect.md has no [[clusters]] block"
    saved_lines = [line.strip() for line in saved.group(1).splitlines() if line.strip()]
    assert len(saved_lines) == 5, saved_lines
    for line in saved_lines:
        assert line in example, f"{line!r} of the Connect block is not in the Results example"
    # The step links to Connect for the file and its folder instead of repeating them.
    assert "connect.md#add-the-cluster-to-sbatchman" in results


# Each topic has one home page. The marker is a string that only the home page may hold.
TOPIC_HOMES = {
    # The `module purge` advice for apps with different module stacks.
    "module purge": "benchmarks",
    # Where the SbatchMan config folder is on each system (other pages may name the file).
    "~/Library/Application Support/sbatchman/": "connect",
    # The first row of the jobs-file key table.
    "SbatchMan runs one job per value": "campaigns",
    # The step that registers a supported benchmark through the wizard.
    "Install or configure a supported benchmark": "launch",
}


def test_every_topic_has_one_home():
    for marker, home in TOPIC_HOMES.items():
        holders = sorted(path.stem for path in _all_docs() if marker in path.read_text())
        assert holders == [home], f"{marker!r} is in {holders}, its home is {home}"


def _section(text: str, heading: str) -> str:
    """The text under `## heading` up to the next `## ` heading (its `###` parts included)."""
    marker = f"\n## {heading}\n"
    assert marker in text, f"no section {heading!r}"
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def _fenced_blocks(text: str, language: str) -> list[str]:
    """The bodies of the fences of `language` (a step may indent the fence), dedented."""
    blocks = re.findall(rf"^[ \t]*```{language}\n(.*?)^[ \t]*```", text, flags=re.DOTALL | re.MULTILINE)
    return [textwrap.dedent(block) for block in blocks]


def _wrapper_example() -> str:
    """The one python block of the "Write the wrapper" section of benchmarks.md."""
    blocks = _fenced_blocks(_section((DOCS / "benchmarks.md").read_text(), "Write the wrapper"), "python")
    assert len(blocks) == 1, f"{len(blocks)} python blocks, expected exactly one"
    return blocks[0]


def test_the_wrapper_example_is_short_and_complete():
    code = _wrapper_example()
    assert 8 <= len(code.splitlines()) <= 16, len(code.splitlines())
    assert "class app(base)" in code
    assert "metadata" in code
    assert "def read_data" in code


def test_the_wrapper_example_never_returns_made_up_numbers():
    code = _wrapper_example()
    assert "raise" in code
    assert "[[0" not in code and "0.0]]" not in code
    # No constant row either: a literal zero as the value of a metric.
    assert not re.search(r":\s*0(\.0)?\s*[,}]", code)


def test_the_wrapper_example_runs(tmp_path):
    # A deliberate skip: the umbrella CI job without submodules installs no crab. The `tests` job runs it.
    pytest.importorskip("crab.wrappers.base")
    text = (DOCS / "benchmarks.md").read_text()
    sample = _fenced_blocks(_section(text, "Write the wrapper"), "text")[0]
    expected = json.loads(_fenced_blocks(_section(text, "Test the wrapper"), "json")[0])
    path = tmp_path / "myapp.py"
    path.write_text(_wrapper_example())
    spec = importlib.util.spec_from_file_location("page_example_wrapper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    wrapper = module.app(0, True, "")
    wrapper.set_output(sample.encode(), b"")
    assert wrapper.read_data() == expected
    assert {metric["name"] for metric in module.app.metadata} == set(expected[0])
    # Output that is not the sample's shape raises: a run fails, nothing made up is recorded.
    for bad in ("", "myapp ranks=4\n", "iteration 1 time_us fast\n"):
        wrapper.set_output(bad.encode(), b"")
        with pytest.raises(ValueError):
            wrapper.read_data()


DASHBOARD_FIELDS = ("Tag", "SbatchMan config", "Nodes", "Processes per node", "Benchmark folder", "Configs file")


def test_the_dashboard_section_does_not_repeat_the_key_table():
    text = (DOCS / "campaigns.md").read_text()
    for field in DASHBOARD_FIELDS:
        assert text.count(f"**{field}**") == 1, field
    # Two sentences of the key tables: each is written once, in the "By hand" section.
    by_hand = _section(text, "By hand")
    for sentence in ("SbatchMan runs one job per value", "The ranks per node of each app"):
        assert text.count(sentence) == 1, sentence
        assert sentence in by_hand, sentence
    dashboard = _section(text, "In the dashboard")
    assert "| Key | Meaning |" not in dashboard
    assert "](#change-the-keys)" in dashboard


def _table_rows(text: str, first_header: str) -> list[list[str]]:
    """The body rows of every table whose header row starts with `| first_header |`, as lists of cells."""
    rows = []
    inside = False
    for line in _outside_fences(text):
        if line.startswith(f"| {first_header} |"):
            inside = True
            continue
        if inside and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not set(cells[0]) <= set("-: "):
                rows.append(cells)
        else:
            inside = False
    return rows


def _documented_fields(text: str) -> set[str]:
    """The first-cell code spans of the field tables of the presets page."""
    return {
        match.group(1) for cells in _table_rows(text, "Field") if (match := re.fullmatch(r"`([^`]+)`", cells[0]))
    }


def _shipped_config_keys() -> set[str]:
    """Every key the shipped template uses: the top-level keys, those of the cluster block, its default_conf
    and each config entry. The cluster's own name is a value chosen by the user, not a field."""
    doc = yaml.safe_load((ROOT / "configs" / "leonardo.yaml").read_text())
    keys: set[str] = set()
    for name, block in doc.items():
        if not (isinstance(block, dict) and "scheduler" in block):
            keys.add(name)
            continue
        keys |= set(block)
        keys |= set(block.get("default_conf", {}))
        for entry in block.get("configs", []):
            keys |= set(entry)
    return keys


# The Slurm fields of a config, copied BY HAND from SbatchMan 2.0.4 (`create_slurm_config` in core/config_manager.py,
# `SlurmConfig` in schedulers/slurm.py). Nothing checks this tuple against SbatchMan: when SbatchMan is bumped,
# compare it with those two places again and update it and docs/presets.md together.
SLURM_FIELDS = (
    "partition", "nodes", "ntasks", "tasks_per_node", "cpus_per_task", "mem", "account", "time", "gpus",
    "constraint", "nodelist", "exclude", "qos", "reservation", "exclusive", "modules", "env", "custom_headers",
)  # fmt: skip


def test_the_presets_page_documents_every_config_field():
    # A key of the shipped template that the field table never names is an undocumented field.
    keys = _shipped_config_keys()
    assert {"variables", "scheduler", "default_conf", "configs", "name", "nodes", "modules", "env"} <= keys
    assert "leonardo" not in keys
    documented = _documented_fields((DOCS / "presets.md").read_text())
    assert sorted(keys - documented) == []


def test_the_presets_page_documents_every_slurm_field_in_the_hand_copied_list():
    documented = _documented_fields((DOCS / "presets.md").read_text())
    assert sorted(set(SLURM_FIELDS) - documented) == []


def test_the_variables_path_rows_say_relative_paths_are_read_from_the_filled_copy():
    # SbatchMan resolves a relative path from the folder of the file it loads: in the umbrella flow that is the
    # filled copy in `.local/`, not the template in `configs/`. A bare file name in an example would not be found.
    text = (DOCS / "presets.md").read_text()
    rows = {cells[0]: cells for cells in _table_rows(text, "Field")}
    for field in ("`variables`", "`include_variables`"):
        assert "read from `.local/`" in rows[field][1], field
    assert "../configs/" in rows["`include_variables`"][2]
    assert "../configs/nodes.txt" in rows["`variables`"][1]


def test_every_field_row_tells_the_meaning_an_example_the_default_and_whether_it_is_required():
    text = (DOCS / "presets.md").read_text()
    assert "| Field | Meaning | Example | Default | Required |" in text
    rows = _table_rows(text, "Field")
    assert len(rows) >= len(SLURM_FIELDS) + 5, len(rows)
    for cells in rows:
        assert len(cells) == 5, cells
        assert all(cells), cells
        assert re.fullmatch(r"`[^`]+`", cells[0]), cells
        assert re.fullmatch(r"`[^`]+`", cells[2]), cells
        assert cells[4] in {"yes", "no"}, cells
    # SbatchMan stops without a config's `name` and without the cluster's `scheduler`: nothing else is required.
    required = sorted(cells[0] for cells in rows if cells[4] == "yes")
    assert required == ["`name`", "`scheduler`"], required


def test_the_presets_page_names_the_four_tokens_that_install_sh_fills():
    script = (ROOT / "install.sh").read_text()
    tokens = set(re.findall(r"token_\w+='<([A-Z_]+)>'", script))
    assert len(tokens) == 4, tokens
    section = _section((DOCS / "presets.md").read_text(), "Tokens the installer fills")
    for token in tokens:
        assert f"`{token}`" in section, token


def test_the_presets_example_adds_a_config_with_documented_fields_only():
    text = (DOCS / "presets.md").read_text()
    blocks = _fenced_blocks(_section(text, "Add your config"), "yaml")
    assert len(blocks) == 1, len(blocks)
    entries = yaml.safe_load(blocks[0])
    assert isinstance(entries, list) and len(entries) == 1
    entry = entries[0]
    assert "{nodes}" in entry["name"]
    assert set(entry) <= _documented_fields(text), set(entry) - _documented_fields(text)
    # The name uses the template's `nodes` variable, so the template must define it.
    assert "nodes" in yaml.safe_load((ROOT / "configs" / "leonardo.yaml").read_text())["variables"]


def test_add_your_config_has_one_home():
    # The section moved from the jobs-file page to the configs-file page: one copy, and a link from the old place.
    heading = re.compile(r"^#{1,6} Add your config\s*$", re.MULTILINE)
    assert [path.stem for path in _all_docs() if heading.search(path.read_text())] == ["presets"]
    campaigns = (DOCS / "campaigns.md").read_text()
    assert "](presets.md#add-your-config)" in campaigns
    assert "campaigns.md#add-your-config" not in "\n".join(path.read_text() for path in _all_docs())
    # The rule that the template is edited and the filled copy is not is written once, on the configs-file page.
    holders = sorted(path.stem for path in _all_docs() if "never the filled copy" in path.read_text())
    assert holders == ["presets"], holders


def test_the_presets_page_has_the_another_cluster_section_and_does_not_edit_the_installer():
    section = _section((DOCS / "presets.md").read_text(), "Another cluster")
    assert 12 <= len(section.splitlines()) <= 40, len(section.splitlines())
    for name in (
        "configs/leonardo.yaml",
        "site/leonardo.env",
        "site/local.env",
        ".local/configs.leonardo.yaml",
        "SBATCHMAN_CLUSTER_NAME",
        "remotes-config.toml",
        "sacctmgr",
        "crab_run_{nodes}",
        "launch.md#register-blink",
    ):
        assert name in section, name
    # What the section says the installer reads is what the installer reads. If the installer ever takes the
    # cluster name as a variable, these fail and the section needs rewriting with it.
    script = (ROOT / "install.sh").read_text()
    for line in (
        'TEMPLATE="$ROOT/configs/leonardo.yaml"',
        'TARGET="$ROOT/.local/configs.leonardo.yaml"',
        '[[ -f "$ROOT/site/leonardo.env" ]] && source "$ROOT/site/leonardo.env"',
        'cluster_name="${SBATCHMAN_CLUSTER_NAME:-leonardo}"',
    ):
        assert line in script, line
    assert "is not read" in section
    # The Leonardo-specific entries the section sends the reader to change are in the shipped template.
    template = (ROOT / "configs" / "leonardo.yaml").read_text()
    for entry in ("CRAB_SYSTEM", "CRAB_IB_DEVICES", "UCX_IB_SL", "NCCL_IB_SL", 'name: "crab_run_{nodes}"'):
        assert entry in template, entry
    for entry in ("CRAB_SYSTEM", "CRAB_IB_DEVICES", "UCX_IB_SL", "NCCL_IB_SL"):
        assert entry in section, entry


PLOTS = DOCS / "plots.md"
SHIPPED_PLOTS = ROOT / "benchmarks" / "blink" / "plots.json"
# The eight plot types of SbatchMan, copied BY HAND from its register_plot(...) calls (the same list as PLOT_TYPES in
# tests/test_plots.py). Nothing checks it against SbatchMan: when SbatchMan is bumped, compare again.
PLOT_TYPES = ("line", "bar", "scatter", "histogram", "box", "violin", "heatmap", "pie")
# What the page tells the reader about a job, copied BY HAND from `Job` in sbatchman/core/job.py (fields and methods).
JOB_FIELDS = ("job.status", "job.tag", "job.config_name", "job.cluster_name", "job.job_id", "job.variables", "job.get_job_base_path()")  # fmt: skip


def _json_keys(value) -> set[str]:
    """Every key of a parsed JSON value, at any depth."""
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(key)
            keys |= _json_keys(item)
    elif isinstance(value, list):
        for item in value:
            keys |= _json_keys(item)
    return keys


def _code_spans(text: str) -> set[str]:
    """The inline code spans of the prose (fenced blocks left out)."""
    return set(re.findall(r"`([^`\n]+)`", "\n".join(_outside_fences(text))))


def test_the_plots_page_names_every_key_of_the_shipped_plots_json():
    keys = _json_keys(json.loads(SHIPPED_PLOTS.read_text()))
    assert {"version", "activeTabIndex", "tabs", "sql", "plotType", "x", "y", "group", "style", "script_paths"} <= keys
    assert sorted(keys - _code_spans(PLOTS.read_text())) == []


def test_the_plots_page_lists_the_plot_types_and_the_job_fields_of_a_parser():
    text = PLOTS.read_text()
    assert sorted(set(PLOT_TYPES) - _code_spans(text)) == []
    assert [name for name in JOB_FIELDS if f"`{name}`" not in text] == []


def test_the_plots_page_names_the_functions_of_the_shared_parser():
    parser = (ROOT / "benchmarks" / "parser.py").read_text()
    text = PLOTS.read_text()
    # `parse(job)` is the one name SbatchMan calls: the page documents it and the shared parser defines it.
    assert re.search(r"^def parse\(job\):", parser, flags=re.MULTILINE)
    assert "`parse(job)`" in text
    assert "`benchmarks/parser.py`" in text
    # The symlink pattern the page gives is the one the shipped Blink folder uses.
    link = ROOT / "benchmarks" / "blink" / "parser.py"
    assert link.is_symlink() and os.readlink(link) == "../parser.py"
    assert "ln -s ../parser.py benchmarks/<benchmark>/parser.py" in [line.strip() for line in _inside_fences(text)]


def test_the_plots_page_example_entry_is_the_first_plot_of_the_blink_file():
    section = _section(PLOTS.read_text(), "The plots.json file")
    blocks = _fenced_blocks(section, "json")
    assert len(blocks) == 1, len(blocks)
    assert json.loads(blocks[0]) == json.loads(SHIPPED_PLOTS.read_text())["tabs"][0]


def test_parser_and_plots_topics_have_one_home():
    # The two sections moved to the plots page: the old headings are gone, each old place points at the new page.
    results = (DOCS / "results.md").read_text()
    benchmarks = (DOCS / "benchmarks.md").read_text()
    assert not re.search(r"^#{1,6} Plot a benchmark of your own\s*$", results, flags=re.MULTILINE)
    assert not re.search(r"^#{1,6} Give the benchmark folder a `parser.py`\s*$", benchmarks, flags=re.MULTILINE)
    assert "](plots.md" in results and "](plots.md" in benchmarks
    markers = (
        "Without `plots.json`, the page opens with no saved plots and you build them in the plot builder.",
        "reads `./parser.py` of the folder you start it from",
        "SQL needs double quotes around a column name that starts with a digit or contains a dash",
        "ln -s ../parser.py benchmarks/<benchmark>/parser.py",
    )
    for marker in markers:
        holders = sorted(path.stem for path in _all_docs() if marker in path.read_text())
        assert holders == ["plots"], f"{marker!r} is in {holders}"
    # The troubleshooting entry for the missing parser keeps its message and one cause, and links to the home.
    for gone in ("ln -s ../parser.py parser.py", "reads `./parser.py`, and only the benchmark folders hold it"):
        assert [path.stem for path in _all_docs() if gone in path.read_text()] == [], gone
    entry = _section((DOCS / "troubleshooting.md").read_text(), "Results").split('### "Parser script not found:"')[1]
    assert "](plots.md#use-the-shared-parser)" in entry.split("\n### ", 1)[0]


def test_the_plots_page_example_runs(tmp_path):
    # The example avoids importing SbatchMan: a job is any object with the fields the page lists, so nothing is skipped.
    section = _section(PLOTS.read_text(), "Write a parser of your own")
    code = _fenced_blocks(section, "python")[0]
    assert 10 <= len(code.splitlines()) <= 20, len(code.splitlines())
    assert "sbatchman" not in code
    job_folder = tmp_path / "job"
    job_folder.mkdir()
    (job_folder / "times.csv").write_text(_fenced_blocks(section, "csv")[0])
    path = tmp_path / "parser.py"
    path.write_text(code)
    spec = importlib.util.spec_from_file_location("page_example_parser", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def job(status="COMPLETED", base=job_folder):
        return SimpleNamespace(
            status=status, tag="myapp-smoke", config_name="myapp_2", variables={"nodes": 2}, get_job_base_path=lambda: base
        )

    rows = module.parse(job())["myapp"]
    shown = next(block for block in _fenced_blocks(section, "text") if "iteration" in block).splitlines()
    assert shown[0].split() == list(rows[0])
    assert [line.split() for line in shown[1:]] == [[str(value) for value in row.values()] for row in rows]
    # A job that did not complete, or whose folder has no times.csv, adds no rows.
    assert module.parse(job("RUNNING")) is None
    assert module.parse(job(base=tmp_path)) is None


# Keys that SbatchMan's plot builder writes (`getNodeConfig` in sbatchman/visualize/static/config.js) and that the Blink
# file does not use. The page must name them, so a reader can find `z` for a heatmap. Copied BY HAND: nothing checks it
# against SbatchMan, so compare it again when SbatchMan is bumped.
BUILDER_KEYS_OUTSIDE_BLINK = ("z", "markerBy", "dashBy", "xScale", "yScale", "legendPosition", "extra")


def test_the_plots_page_names_the_builder_keys_outside_the_blink_file_and_the_keys_of_each_plot_type():
    text = PLOTS.read_text()
    assert sorted(set(BUILDER_KEYS_OUTSIDE_BLINK) - _code_spans(text)) == []
    # One sentence says which keys each plot type needs (read from the plot functions of SbatchMan's utils/plots.py).
    needs = next(line for line in text.splitlines() if line.startswith("`line`, `bar` and `scatter` need"))
    for plot_type in PLOT_TYPES:
        assert f"`{plot_type}`" in needs, plot_type
    assert "`heatmap` needs `x`, `y` and `z`" in needs


def test_the_plots_page_gets_the_reader_from_a_parser_to_plots_without_pitfalls():
    text = PLOTS.read_text()
    # Saving a file over the symlink overwrites the shared parser: the page removes the link first, before the code.
    section = _section(text, "Write a parser of your own")
    assert "rm benchmarks/<benchmark>/parser.py" in [line.strip() for line in _inside_fences(section)]
    assert section.index("rm benchmarks/<benchmark>/parser.py") < section.index("```python")
    assert "overwrites the shared `benchmarks/parser.py`" in section
    # A job reaches its job folder through $SBATCHMAN_JOB_DIR, which the jobs-file page documents.
    assert "`$SBATCHMAN_JOB_DIR`" in section and "](campaigns.md#change-the-keys)" in section
    assert "$SBATCHMAN_JOB_DIR" in _section((DOCS / "campaigns.md").read_text(), "By hand")
    # The address to open, as on the results page.
    assert "`http://127.0.0.1:8765`" in text and "http://127.0.0.1:8765" in (DOCS / "results.md").read_text()
    # An export writes the user's own script folders into the file.
    assert "delete the entries that name your own folders before you commit `plots.json`" in text
    # The contract: falsy returns skip the job, and a wrong table value stops the run.
    assert "any other falsy value" in text and "something other than a row or a list of rows in a table" in text
    # Why a page opens empty with a plots.json present.
    empty = next(line for line in text.splitlines() if line.startswith("- The page opens empty although `plots.json` is there"))
    assert "`Failed to load`" in empty and "`--presets`" in empty and "Only `./plots.json`" in empty


def test_the_advanced_section_lists_reference_configs_and_plots():
    nav = yaml.safe_load((ROOT / "mkdocs.yml").read_text())["nav"]
    advanced = next(entry["Advanced"] for entry in nav if isinstance(entry, dict) and "Advanced" in entry)
    assert advanced == ["reference.md", "presets.md", "plots.md"]
    assert "](plots.md" in (DOCS / "index.md").read_text()


def _glossary_terms() -> list[str]:
    """The first cells of the glossary table, in file order."""
    return [cells[0] for cells in _table_rows((DOCS / "glossary.md").read_text(), "Word")]


def test_the_glossary_has_one_home():
    # The glossary moved from the reference page to its own page in the Help section: one copy, no link left behind.
    glossary = DOCS / "glossary.md"
    assert glossary.is_file()
    assert glossary.read_text().splitlines()[0] == "# Glossary"
    assert _h1_count(glossary.read_text()) == 1
    heading = re.compile(r"^#{1,6} Glossary\s*$", re.MULTILINE)
    assert [path.stem for path in _all_docs() if heading.search(path.read_text())] == ["glossary"]
    assert "reference.md#glossary" not in "\n".join(path.read_text() for path in _all_docs())
    assert "words the docs use" not in (DOCS / "reference.md").read_text()


def test_every_glossary_term_is_used_in_the_docs():
    # A row for a word that no page uses is clutter: each term occurs in a page other than the glossary.
    terms = _glossary_terms()
    assert len(terms) >= 12, terms
    others = "\n".join(path.read_text() for path in PAGE_PATHS if path.stem != "glossary").lower()
    assert [term for term in terms if term.lower() not in others] == []


def test_the_glossary_defines_the_words_the_docs_use_without_explaining():
    terms = {term.lower() for term in _glossary_terms()}
    wanted = {
        "umbrella", "campaign", "jobs file", "tag", "receipt", "wrapper", "cluster profile", "login node",
        "slurm account", "sbatchman project", "fetch", "dashboard", "config", "configs file", "self-check",
    }  # fmt: skip
    assert sorted(wanted - terms) == []


def test_the_glossary_is_alphabetical_and_each_row_has_a_meaning_and_no_repeat():
    text = (DOCS / "glossary.md").read_text()
    terms = _glossary_terms()
    assert terms == sorted(terms, key=str.lower)
    assert len({term.lower() for term in terms}) == len(terms)
    for cells in _table_rows(text, "Word"):
        assert len(cells) == 2 and all(cells), cells
        assert cells[1].endswith("."), cells


def test_the_help_section_lists_troubleshooting_and_glossary():
    nav = yaml.safe_load((ROOT / "mkdocs.yml").read_text())["nav"]
    titles = [next(iter(entry)) for entry in nav if isinstance(entry, dict)]
    assert titles[-1] == "Help"
    help_section = next(entry["Help"] for entry in nav if isinstance(entry, dict) and "Help" in entry)
    assert help_section == ["troubleshooting.md", "glossary.md"]
    assert "](glossary.md" in (DOCS / "index.md").read_text()
    assert "(docs/glossary.md)" in README.read_text()
