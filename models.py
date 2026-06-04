from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class Priority(Enum):

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        """Numeric rank for sorting (higher == more urgent)."""
        return {"low": 0, "medium": 1, "high": 2}[self.value]

    @classmethod
    def from_str(cls, raw: str) -> "Priority":
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            valid = ", ".join(p.value for p in cls)
            raise ValueError(f"Invalid priority '{raw}'. Choose from: {valid}") from exc


class Status(Enum):

    PENDING = "pending"
    DONE = "done"

    @classmethod
    def from_str(cls, raw: str) -> "Status":
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            valid = ", ".join(s.value for s in cls)
            raise ValueError(f"Invalid status '{raw}'. Choose from: {valid}") from exc


class Recurrence(Enum):

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

    @classmethod
    def from_str(cls, raw: str) -> "Recurrence":
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            valid = ", ".join(r.value for r in cls)
            raise ValueError(f"Invalid recurrence '{raw}'. Choose from: {valid}") from exc

    def next_occurrence(self, after: datetime) -> Optional[datetime]:
        if self is Recurrence.NONE:
            return None
        if self is Recurrence.DAILY:
            return after + timedelta(days=1)
        if self is Recurrence.WEEKLY:
            return after + timedelta(weeks=1)
        if self is Recurrence.MONTHLY:
            return add_months(after, 1)
        if self is Recurrence.YEARLY:
            return add_months(after, 12)
        return None


def add_months(dt: datetime, months: int) -> datetime:
    zero_based = dt.month - 1 + months
    year = dt.year + zero_based // 12
    month = zero_based % 12 + 1
    day = min(dt.day, days_in_month(year, month))
    return dt.replace(year=year, month=month, day=day)


def days_in_month(year: int, month: int) -> int:
    if month == 12:
        nxt = datetime(year + 1, 1, 1)
    else:
        nxt = datetime(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last.day


@dataclass
class Task:
    title: str
    due: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    status: Status = Status.PENDING
    recurrence: Recurrence = Recurrence.NONE
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        """True if the task is pending and its due date has passed."""
        if self.due is None or self.status is Status.DONE:
            return False
        return self.due < (now or datetime.now())
