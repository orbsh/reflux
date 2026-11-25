"""The two language trees: same application, one language each.

The rule the trees are built on is a reader's: open the tree for your language and find nothing else in
it — UI text, comments and docstrings all in that language. Code cannot check prose's language, so these
cases check what can be checked: the two trees draw the same page (same node ids, in the same places),
and each is CJK-free or CJK-only as its tree says.

A tree is a site, and a site is one app per process (`reflux.site`), so the two trees cannot be imported
into one interpreter — both would register `/` and `/v1/inspect` on the same app. The comparison
therefore runs each tree in its own process, which is also how they are served.
"""

from __future__ import annotations

import functools
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.fakes import ids, texts

ROOT = Path(__file__).resolve().parents[1]

CJK = re.compile(r"[\u4e00-\u9fff]")
ANY = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")  # CJK text or punctuation
WORD = re.compile(r"[A-Za-z]{3,}")  # a run of letters, i.e. an English word
PAGES = ("/", "/about", "/chat", "/counter", "/demo", "/settings")


@functools.cache
def drawn(package: str) -> dict:
    """One tree, drawn in its own process: its routes, and each page's ids and texts.

    Cached: a page is a real draw, and the two cases below (`same tree`, `the words differ`) both want
    the same picture.
    """
    script = f"""
import json
from tests.fakes import ids, page_nodes, texts
from {package}.demo_app import app

answer = {{"routes": [route.path for route in app.routes], "pages": {{}}}}
for path in {list(PAGES)!r}:
    nodes = page_nodes(app, path)
    answer["pages"][path] = {{"ids": ids(nodes), "texts": texts(nodes)}}
print(json.dumps(answer, ensure_ascii=False))
"""
    run = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    if run.returncode != 0:
        raise AssertionError(f"{package} did not answer in its own process:\n{run.stderr[-1200:]}")
    return json.loads(run.stdout)


def texts(nodes: list[dict]) -> list[str]:
    """Every `default` text the page carries — what a reader actually sees."""
    out: list[str] = []

    def walk(node) -> None:
        if isinstance(node, (list, tuple)):
            for kid in node:
                walk(kid)
            return
        if not isinstance(node, dict):
            return
        source = node.get("source")
        if isinstance(source, dict) and isinstance(source.get("default"), str):
            out.append(source["default"])
        walk(node.get("children") or [])

    walk(nodes)
    return out


def comments(path: Path) -> list[tuple[int, str]]:
    """Every comment in a file, full-line or trailing — the prose a reader also reads.

    Read through `tokenize`, not `str.find("#")`: a `#` inside a string (a colour literal, a CSS
    selector) is a value, not a comment, and judging it as prose flags correct code.
    """
    import io
    import tokenize

    out: list[tuple[int, str]] = []
    source = path.read_text(encoding="utf-8")
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type != tokenize.COMMENT:
                continue
            body = token.string
            if body.startswith(("# noqa", "# type:", "#!")):
                continue  # a directive, not prose
            out.append((token.start[0], body))
    except (tokenize.TokenError, IndentationError):
        return out
    return out


def is_code(body: str) -> bool:
    """A docstring that is really a code sample: Rust, JS or Python with nothing to read as prose."""
    first = body.strip().splitlines()[0]
    return bool(re.search(r"(fn |pub |->|;\s*$|\{\s*$)", body)) and not CJK.search(first)


def docstrings(path: Path) -> list[tuple[int, str]]:
    """Every triple-quoted block in a file, with the line it opens on — enough to tell prose languages."""
    text = path.read_text(encoding="utf-8")
    return [
        (text[: match.start()].count("\n") + 1, match.group(1).strip())
        for match in re.finditer(r'"""(.*?)"""', text, re.S)
        if match.group(1).strip()
    ]


class SameShape(unittest.TestCase):
    def test_the_two_trees_declare_the_same_pages(self) -> None:
        self.assertEqual(drawn("examples.zh")["routes"], list(PAGES))
        self.assertEqual(drawn("examples.en")["routes"], list(PAGES))

    def test_every_page_draws_the_same_tree_in_both_trees(self) -> None:
        zh, en = drawn("examples.zh")["pages"], drawn("examples.en")["pages"]
        for path in PAGES:
            with self.subTest(path=path):
                self.assertEqual(en[path]["ids"], zh[path]["ids"],
                                 "the two trees must be the same page: same ids, same order")

    def test_the_words_are_the_ones_that_differ(self) -> None:
        english = " ".join(drawn("examples.en")["pages"]["/"]["texts"])
        chinese = " ".join(drawn("examples.zh")["pages"]["/"]["texts"])
        self.assertTrue(english and chinese)
        self.assertFalse(CJK.search(english), f"Chinese left in the English page: {english[:80]}")
        self.assertTrue(CJK.search(chinese), "the Chinese page has no Chinese in it")

    def test_two_trees_are_two_sites(self) -> None:
        """Not a limitation to work around: the second tree's import is what says they are two sites."""
        both = subprocess.run(
            [sys.executable, "-c", "import examples.zh.demo_app, examples.en.demo_app"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
        self.assertNotEqual(both.returncode, 0)
        self.assertIn("already", both.stderr, "the collision has to name itself")


class Sources(unittest.TestCase):
    """What a reader opening the tree sees: a stray sentence in the other language is a bug."""

    def tree(self, package) -> list[Path]:
        root = Path(package.__file__).parent
        return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)

    def test_the_chinese_tree_speaks_chinese_in_its_docstrings_and_comments(self) -> None:
        # Docstrings and comments are prose for the reader of that tree: in `examples/zh/` they are
        # Chinese, in `examples/en/` English (the case below). Identifiers and wire words stay as
        # they are, so a line is judged by whether it contains any Chinese at all — a path list in a
        # comment (`# /、/about`) counts, a sentence of English does not.
        import examples.zh as package

        for path in self.tree(package):
            for number, body in comments(path):
                if WORD.search(body) and not ANY.search(body):
                    self.fail(
                        f"{path.relative_to(Path.cwd())}:{number} is not Chinese: {body.strip()[:70]}"
                    )
            for number, body in docstrings(path):
                if is_code(body):
                    continue  # a code sample inside the docstring is not prose
                # A docstring is judged as a whole, by proportion: Chinese prose run through a
                # tangle of identifiers still reads as Chinese, while an English paragraph that
                # quotes one wire word (`退出`) does not become Chinese by containing it.
                if len(CJK.findall(body)) < 2 * len(WORD.findall(body)):
                    self.fail(
                        f"{path.relative_to(Path.cwd())}:{number} is not written in Chinese: "
                        f"{body.strip().splitlines()[0][:70]}"
                    )

    def test_the_english_tree_carries_no_chinese(self) -> None:
        import examples.en as package

        for path in self.tree(package):
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), 1):
                if CJK.search(line):
                    self.fail(f"{path.relative_to(Path.cwd())}:{number} is not English: {line.strip()[:70]}")



if __name__ == "__main__":
    unittest.main()