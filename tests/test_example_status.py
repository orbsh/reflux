"""The example's operator endpoint, offline: it is a plain function, so no server is needed here.

`tools/gate_dashboard.py` hits the same route over real HTTP; these cases keep the fast suite honest
about what `/status` promises without starting anything.
"""

from __future__ import annotations

import json
import unittest

from examples.app.app import status
from reflux.server import Request


class TestStatus(unittest.TestCase):
    def setUp(self) -> None:
        self.answer = status(Request(method="GET", path="/status"))
        self.body = json.loads(self.answer.body)

    def test_it_answers_json_with_the_pages(self):
        self.assertEqual(self.answer.status, 200)
        self.assertEqual(self.answer.content_type, "application/json")
        self.assertEqual(sorted(self.body["routes"]), ["/", "/chat"])

    def test_it_reports_the_table_the_counters_and_the_modules(self):
        self.assertIn("/status", self.body["mounts"])
        self.assertIn("/ws", self.body["mounts"])
        self.assertEqual(
            sorted(self.body["stats"]),
            ["dead", "issued", "reclaimed", "refused", "resync", "shed"],
        )
        self.assertIsInstance(self.body["devices"], int)
        self.assertEqual(sorted(self.body["modules"]), ["charts", "viewer"])
        # Slots are declared where they are used, so the listing only shows ones a page has touched —
        # what is declared here is this app's, not a table anyone maintained by hand.
        self.assertIsInstance(self.body["slots"], list)
        self.assertTrue(set(self.body["slots"]) <= {"status", "messages"} | set(self.body["slots"]))


if __name__ == "__main__":
    unittest.main()