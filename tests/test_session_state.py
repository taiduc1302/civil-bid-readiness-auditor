import threading
import unittest

from app.session_state import clear_session_locks, expire_sessions, register_session, session_scope


class SessionStateTests(unittest.TestCase):
    def setUp(self):
        clear_session_locks()
        self.sessions = {}

    def tearDown(self):
        clear_session_locks()

    def test_valid_access_refreshes_idle_timeout(self):
        register_session(self.sessions, "token", {"value": 1}, now=100.0)
        self.assertEqual(self.sessions["token"]["created"], 100.0)
        self.assertEqual(self.sessions["token"]["last_access"], 100.0)

        with session_scope(self.sessions, "token", 30.0, now=120.0) as session:
            self.assertIsNotNone(session)
            self.assertEqual(session["value"], 1)
        self.assertEqual(self.sessions["token"]["last_access"], 120.0)

        self.assertEqual(expire_sessions(self.sessions, 30.0, now=149.0), [])
        self.assertIn("token", self.sessions)
        self.assertEqual(expire_sessions(self.sessions, 30.0, now=151.0), ["token"])
        self.assertNotIn("token", self.sessions)

    def test_expired_lookup_fails_closed(self):
        register_session(self.sessions, "token", {"value": 1}, now=100.0)
        with session_scope(self.sessions, "token", 30.0, now=131.0) as session:
            self.assertIsNone(session)
        self.assertNotIn("token", self.sessions)

    def test_different_sessions_do_not_share_one_lock(self):
        register_session(self.sessions, "one", {"value": 1}, now=100.0)
        register_session(self.sessions, "two", {"value": 2}, now=100.0)
        first_entered = threading.Event()
        release_first = threading.Event()
        second_entered = threading.Event()

        def first():
            with session_scope(self.sessions, "one", 30.0, now=101.0):
                first_entered.set()
                release_first.wait(1.0)

        def second():
            with session_scope(self.sessions, "two", 30.0, now=101.0):
                second_entered.set()

        thread_one = threading.Thread(target=first)
        thread_two = threading.Thread(target=second)
        thread_one.start()
        self.assertTrue(first_entered.wait(1.0))
        thread_two.start()
        self.assertTrue(second_entered.wait(1.0))
        release_first.set()
        thread_one.join(1.0)
        thread_two.join(1.0)
        self.assertFalse(thread_one.is_alive())
        self.assertFalse(thread_two.is_alive())

    def test_same_session_scope_serializes_mutation(self):
        register_session(self.sessions, "token", {"value": 0}, now=100.0)
        first_entered = threading.Event()
        release_first = threading.Event()
        second_started = threading.Event()
        second_entered = threading.Event()

        def first():
            with session_scope(self.sessions, "token", 30.0, now=101.0) as session:
                session["value"] = 1
                first_entered.set()
                release_first.wait(1.0)
                session["value"] = 2

        def second():
            second_started.set()
            with session_scope(self.sessions, "token", 30.0, now=102.0) as session:
                second_entered.set()
                session["value"] += 10

        thread_one = threading.Thread(target=first)
        thread_two = threading.Thread(target=second)
        thread_one.start()
        self.assertTrue(first_entered.wait(1.0))
        thread_two.start()
        self.assertTrue(second_started.wait(1.0))
        self.assertFalse(second_entered.wait(0.05))
        release_first.set()
        self.assertTrue(second_entered.wait(1.0))
        thread_one.join(1.0)
        thread_two.join(1.0)
        self.assertEqual(self.sessions["token"]["value"], 12)

    def test_expirer_skips_session_currently_in_use(self):
        register_session(self.sessions, "token", {"value": 1}, now=100.0)
        entered = threading.Event()
        release = threading.Event()

        def worker():
            with session_scope(self.sessions, "token", 30.0, now=120.0):
                entered.set()
                release.wait(1.0)

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(entered.wait(1.0))
        # Even though this synthetic clock is far past the stored access time,
        # expiry must not remove a session while a request owns its lock.
        self.assertEqual(expire_sessions(self.sessions, 30.0, now=200.0), [])
        self.assertIn("token", self.sessions)
        release.set()
        thread.join(1.0)


if __name__ == "__main__":
    unittest.main()
