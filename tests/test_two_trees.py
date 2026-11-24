"""The two language trees: same application, one language each.

The rule the trees are built on is a reader's: open the tree for your language and find nothing else in
it — UI text, comments and docstrings all in that language. Code cannot check prose's language, so these
cases check what can be checked: the two trees draw the same page (same node ids, in the same places),
each is CJK-free or CJK-only as its tree says, and the two apps are separate route tables so both can
serve `/` at once.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from examples.en import demo_app as en_app
from examples.zh import demo_app as zh_app
from tests.fakes import page_nodes

CJK = re.compile(r"[\u4e00-\u9fff]")
PAGES = ("/", "/about", "/chat", "/demo")


def ids(nodes: list[dict]) -> list[str]:
    """Every node id in a subtree, depth first — the shape of the page, without its words."""
    out: list[str] = []

    def walk(node) -> None:
        if isinstance(node, (list, tuple)):
            for kid in node:
                walk(kid)
            return
        if not isinstance(node, dict):
            return
        if "id" in node:
            out.append(node["id"])
        walk(node.get("children") or [])

    walk(nodes)
    return out


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
        self.assertEqual([r.path for r in zh_app.make_app().routes], list(PAGES))
        self.assertEqual([r.path for r in en_app.make_app().routes], list(PAGES))

    def test_every_page_draws_the_same_tree_in_both_trees(self) -> None:
        for path in PAGES:
            with self.subTest(path=path):
                self.assertEqual(
                    ids(page_nodes(en_app.make_app(), path)),
                    ids(page_nodes(zh_app.make_app(), path)),
                    "the two trees must be the same page: same ids, same order",
                )

    def test_the_words_are_the_ones_that_differ(self) -> None:
        english = " ".join(texts(page_nodes(en_app.make_app(), "/")))
        chinese = " ".join(texts(page_nodes(zh_app.make_app(), "/")))
        self.assertTrue(english and chinese)
        self.assertFalse(CJK.search(english), f"Chinese left in the English page: {english[:80]}")
        self.assertTrue(CJK.search(chinese), "the Chinese page has no Chinese in it")

    def test_the_two_apps_are_separate_tables(self) -> None:
        self.assertIsNot(zh_app.make_app(), en_app.make_app())
        self.assertIsNot(zh_app.make_app().routes, en_app.make_app().routes)


class Sources(unittest.TestCase):
    """What a reader opening the tree sees: a stray sentence in the other language is a bug."""

    def tree(self, package) -> list[Path]:
        root = Path(package.__file__).parent
        return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)

    def test_the_chinese_tree_speaks_chinese_in_its_docstrings(self) -> None:
        # A docstring is prose for the reader of that tree: in `examples/zh/` it is Chinese, in
        # `examples/en/` it is English (the case below). Identifiers and wire words stay as they are.
        import examples.zh as package

        for path in self.tree(package):
            for number, body in docstrings(path):
                if not CJK.search(body):
                    self.fail(
                        f"{path.relative_to(Path.cwd())}:{number} has an English docstring: {body[:70]}"
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