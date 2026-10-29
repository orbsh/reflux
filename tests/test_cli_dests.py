"""The event registry: registration is startup-loud, dispatch is the only authority.

An event name is an address. These tests pin both halves of that: a registration that can never
be right fails while the app is still starting (reserved prefix, duplicate, not callable), and a
frame whose name nobody registered is refused, counted and logged — never dispatched, never
silently swallowed.
"""

from __future__ import annotations

import unittest

from reflux.dests import Registry, RegistryError

from tests.fakes import FakeSession


class TestRegistration(unittest.TestCase):
    def test_reserved_prefix_is_a_startup_error(self) -> None:
        events = Registry()
        with self.assertRaises(RegistryError) as caught:
            events.register("reflux:nav", lambda session, frame: None)
        self.assertIn("reserved prefix", str(caught.exception))
        self.assertEqual(events.names(), [])

    def test_the_framework_may_use_the_reserved_prefix(self) -> None:
        events = Registry()
        events.builtin("reflux:hello", lambda session, frame: None)
        self.assertEqual(events.names(), ["reflux:hello"])

    def test_duplicate_registration_is_an_error_not_an_overwrite(self) -> None:
        events = Registry()
        events.register("chat.send", lambda session, frame: None)
        with self.assertRaises(RegistryError):
            events.register("chat.send", lambda session, frame: None)

    def test_names_must_be_non_empty_strings_and_handlers_callable(self) -> None:
        events = Registry()
        with self.assertRaises(RegistryError):
            events.register("", lambda session, frame: None)
        with self.assertRaises(RegistryError):
            events.register("chat.send", "not callable")  # type: ignore[arg-type]

    def test_decorator_form_registers(self) -> None:
        events = Registry()

        @events.register("chat.send")
        def handler(session, frame) -> None:
            session.seen.append(frame)

        self.assertEqual(events.names(), ["chat.send"])
        session = FakeSession()
        self.assertTrue(events.dispatch(session, {"dest": "chat.send", "data": {}}))
        self.assertEqual(len(session.seen), 1)


class TestDispatch(unittest.TestCase):
    def test_unregistered_name_is_refused_counted_and_logged(self) -> None:
        events = Registry()
        session = FakeSession()
        self.assertFalse(events.dispatch(session, {"dest": "ghost.press", "id": None, "data": {}}))
        self.assertEqual(events.refused, 1)
        self.assertEqual(events.calls, 0)
        self.assertIn("ghost.press", events.log[-1])
        self.assertIn(session.id, events.log[-1])

    def test_malformed_frame_is_refused(self) -> None:
        events = Registry()
        for bad in ("not a frame", [], {"id": None}, {"dest": 7}):
            with self.subTest(frame=bad):
                self.assertFalse(events.dispatch(FakeSession(), bad))
        self.assertEqual(events.refused, 4)

    def test_a_handler_that_raises_keeps_the_session(self) -> None:
        events = Registry()

        def boom(session, frame) -> None:
            raise RuntimeError("bad handler")

        events.register("boom.now", boom)
        session = FakeSession()
        self.assertFalse(events.dispatch(session, {"dest": "boom.now", "data": {}}))
        self.assertIn("bad handler", events.log[-1])
        # and the next frame still gets through: a defect is a log line, not a dead session
        events.register("fine.now", lambda session, frame: None)
        self.assertTrue(events.dispatch(session, {"dest": "fine.now", "data": {}}))


if __name__ == "__main__":
    unittest.main()