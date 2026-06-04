from __future__ import annotations
import os
import tempfile
import unittest
from datetime import datetime

from taskmaster.db import get_connection
from taskmaster.dates import parse_due
from taskmaster.models import Priority, Recurrence, Status, Task, _add_months
from taskmaster.repository import TaskRepository


class DateParsingTests(unittest.TestCase):
    def test_blank_is_none(self):
        self.assertIsNone(parse_due(""))
        self.assertIsNone(parse_due("   "))

    def test_strict_iso(self):
        self.assertEqual(parse_due("2025-12-25 08:00"), datetime(2025, 12, 25, 8, 0))

    def test_next_weekday_lands_in_future(self):
        result = parse_due("next monday 9am")
        self.assertIsNotNone(result)
        self.assertEqual(result.weekday(), 0)  # Monday
        self.assertEqual((result.hour, result.minute), (9, 0))
        self.assertGreater(result, datetime.now())

    def test_unparseable_raises(self):
        with self.assertRaises(ValueError):
            parse_due("sometime-ish whenever")


class RecurrenceTests(unittest.TestCase):
    def test_none_has_no_next(self):
        self.assertIsNone(Recurrence.NONE.next_occurrence(datetime(2025, 1, 1)))

    def test_daily(self):
        nxt = Recurrence.DAILY.next_occurrence(datetime(2025, 1, 1, 9, 0))
        self.assertEqual(nxt, datetime(2025, 1, 2, 9, 0))

    def test_weekly(self):
        nxt = Recurrence.WEEKLY.next_occurrence(datetime(2025, 1, 1))
        self.assertEqual(nxt, datetime(2025, 1, 8))

    def test_monthly_clamps_to_short_month(self):
        # Jan 31 + 1 month should land on Feb 28 (2025 is not a leap year).
        nxt = Recurrence.MONTHLY.next_occurrence(datetime(2025, 1, 31))
        self.assertEqual(nxt, datetime(2025, 2, 28))

    def test_yearly_handles_leap_day(self):
        # Feb 29 2024 + 1 year clamps to Feb 28 2025.
        nxt = Recurrence.YEARLY.next_occurrence(datetime(2024, 2, 29))
        self.assertEqual(nxt, datetime(2025, 2, 28))

    def test_add_months_rolls_over_year(self):
        self.assertEqual(_add_months(datetime(2025, 11, 15), 2), datetime(2026, 1, 15))


class TaskModelTests(unittest.TestCase):
    def test_overdue_true_when_past_and_pending(self):
        t = Task(title="x", due=datetime(2000, 1, 1))
        self.assertTrue(t.is_overdue(now=datetime(2025, 1, 1)))

    def test_overdue_false_when_done(self):
        t = Task(title="x", due=datetime(2000, 1, 1), status=Status.DONE)
        self.assertFalse(t.is_overdue(now=datetime(2025, 1, 1)))

    def test_priority_from_str_invalid(self):
        with self.assertRaises(ValueError):
            Priority.from_str("urgent")


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        # Use a real temp file so each test is isolated.
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.environ["TASKMASTER_DB"] = self.path
        self.conn = get_connection()
        self.repo = TaskRepository(self.conn)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.path)
        os.environ.pop("TASKMASTER_DB", None)

    def test_add_assigns_id(self):
        t = self.repo.add(Task(title="Buy milk"))
        self.assertIsNotNone(t.id)

    def test_get_round_trip_preserves_fields(self):
        original = Task(
            title="Pay rent",
            due=datetime(2025, 6, 1, 9, 0),
            priority=Priority.HIGH,
            recurrence=Recurrence.MONTHLY,
            tags=["finance", "home"],
            notes="bank transfer",
        )
        saved = self.repo.add(original)
        fetched = self.repo.get(saved.id)
        self.assertEqual(fetched.title, "Pay rent")
        self.assertEqual(fetched.priority, Priority.HIGH)
        self.assertEqual(fetched.recurrence, Recurrence.MONTHLY)
        self.assertEqual(fetched.tags, ["finance", "home"])
        self.assertEqual(fetched.due, datetime(2025, 6, 1, 9, 0))

    def test_update(self):
        t = self.repo.add(Task(title="Draft"))
        t.title = "Final"
        t.priority = Priority.LOW
        self.repo.update(t)
        self.assertEqual(self.repo.get(t.id).title, "Final")
        self.assertEqual(self.repo.get(t.id).priority, Priority.LOW)

    def test_delete(self):
        t = self.repo.add(Task(title="temp"))
        self.assertTrue(self.repo.delete(t.id))
        self.assertIsNone(self.repo.get(t.id))
        self.assertFalse(self.repo.delete(t.id))

    def test_complete_one_off_marks_done(self):
        t = self.repo.add(Task(title="once"))
        done = self.repo.complete(t.id)
        self.assertEqual(done.status, Status.DONE)

    def test_complete_recurring_advances_due(self):
        t = self.repo.add(
            Task(
                title="standup",
                due=datetime(2025, 1, 6, 9, 0),
                recurrence=Recurrence.WEEKLY,
            )
        )
        result = self.repo.complete(t.id)
        self.assertEqual(result.status, Status.PENDING)
        self.assertEqual(result.due, datetime(2025, 1, 13, 9, 0))

    def test_filter_by_tag(self):
        self.repo.add(Task(title="a", tags=["work"]))
        self.repo.add(Task(title="b", tags=["home"]))
        results = self.repo.list(tag="work")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "a")

    def test_filter_by_status_and_search(self):
        self.repo.add(Task(title="write report", notes="quarterly"))
        t2 = self.repo.add(Task(title="ignore me"))
        self.repo.complete(t2.id)
        pending = self.repo.list(status=Status.PENDING)
        self.assertEqual(len(pending), 1)
        found = self.repo.list(search="quarterly")
        self.assertEqual(len(found), 1)

    def test_clear_completed(self):
        a = self.repo.add(Task(title="a"))
        self.repo.add(Task(title="b"))
        self.repo.complete(a.id)
        removed = self.repo.clear_completed()
        self.assertEqual(removed, 1)
        self.assertEqual(len(self.repo.list()), 1)

    def test_all_tags_deduplicates(self):
        self.repo.add(Task(title="a", tags=["work", "urgent"]))
        self.repo.add(Task(title="b", tags=["work"]))
        self.assertEqual(self.repo.all_tags(), ["urgent", "work"])


if __name__ == "__main__":
    unittest.main()
