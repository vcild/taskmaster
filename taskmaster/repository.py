from __future__ import annotations
import sqlite3
from datetime import datetime
from typing import Iterable, Optional

from .models import Priority, Recurrence, Status, Task


def serialize_tags(tags: Iterable[str]) -> str:
    cleaned = [t.strip().lower() for t in tags if t.strip()]
    seen: dict[str, None] = {}
    for tag in cleaned:
        seen.setdefault(tag, None)
    return ",".join(seen.keys())


def deserialize_tags(raw: str) -> list[str]:
    return [t for t in (raw or "").split(",") if t]


def row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        due=datetime.fromisoformat(row["due"]) if row["due"] else None,
        priority=Priority.from_str(row["priority"]),
        status=Status.from_str(row["status"]),
        recurrence=Recurrence.from_str(row["recurrence"]),
        tags=deserialize_tags(row["tags"]),
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, task: Task) -> Task:
        """Insert a new task and return it with its assigned ``id``."""
        cur = self.conn.execute(
            """
            INSERT INTO tasks
                (title, due, priority, status, recurrence, tags, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.title,
                task.due.isoformat() if task.due else None,
                task.priority.value,
                task.status.value,
                task.recurrence.value,
                serialize_tags(task.tags),
                task.notes,
                task.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        task.id = cur.lastrowid
        return task

    def get(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return row_to_task(row) if row else None

    def list(
        self,
        *,
        status: Optional[Status] = None,
        priority: Optional[Priority] = None,
        tag: Optional[str] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> list[Task]:
        """Return tasks matching the given filters (all optional, AND-combined).
        Results are ordered by status (pending first), then due date (soonest
        first, undated last), then priority (most urgent first).
        """
        clauses: list[str] = []
        params: list[object] = []

        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if priority is not None:
            clauses.append("priority = ?")
            params.append(priority.value)
        if tag is not None:
            # Match the tag as a whole comma-delimited token.
            clauses.append(
                "(',' || tags || ',') LIKE ?"
            )
            params.append(f"%,{tag.strip().lower()},%")
        if due_before is not None:
            clauses.append("due IS NOT NULL AND due <= ?")
            params.append(due_before.isoformat())
        if due_after is not None:
            clauses.append("due IS NOT NULL AND due >= ?")
            params.append(due_after.isoformat())
        if search:
            clauses.append("(title LIKE ? OR notes LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM tasks {where}", params
        ).fetchall()

        tasks = [row_to_task(r) for r in rows]
        tasks.sort(key=sort_key)
        return tasks

    def update(self, task: Task) -> Task:
        if task.id is None:
            raise ValueError("Cannot update a task without an id.")
        self.conn.execute(
            """
            UPDATE tasks SET
                title = ?, due = ?, priority = ?, status = ?,
                recurrence = ?, tags = ?, notes = ?
            WHERE id = ?
            """,
            (
                task.title,
                task.due.isoformat() if task.due else None,
                task.priority.value,
                task.status.value,
                task.recurrence.value,
                serialize_tags(task.tags),
                task.notes,
                task.id,
            ),
        )
        self.conn.commit()
        return task

    def complete(self, task_id: int) -> Optional[Task]:
        task = self.get(task_id)
        if task is None:
            return None

        if task.recurrence is not Recurrence.NONE and task.due is not None:
            nxt = task.recurrence.next_occurrence(task.due)
            task.due = nxt
            task.status = Status.PENDING
        else:
            task.status = Status.DONE
        return self.update(task)

    def delete(self, task_id: int) -> bool:
        """Delete a task by ID"""
        cur = self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def clear_completed(self) -> int:
        """Delete all done (non-recurring) tasks -> Returns the count removed."""
        cur = self.conn.execute("DELETE FROM tasks WHERE status = 'done'")
        self.conn.commit()
        return cur.rowcount

    def all_tags(self) -> list[str]:
        """Return the sorted set of tags currently in use."""
        rows = self.conn.execute(
            "SELECT tags FROM tasks WHERE tags != ''"
        ).fetchall()
        tags: set[str] = set()
        for r in rows:
            tags.update(deserialize_tags(r["tags"]))
        return sorted(tags)


def sort_key(task: Task):

    status_order = 0 if task.status is Status.PENDING else 1
    due_key = task.due or datetime.max
    return (status_order, due_key, -task.priority.rank)
