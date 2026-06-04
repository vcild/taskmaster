from __future__ import annotations
import sqlite3
from datetime import datetime
from typing import Callable, Optional

from .dates import format_due, parse_due
from .models import Priority, Recurrence, Status, Task
from .repository import TaskRepository


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{label}{suffix}: ").strip()
    return raw or default


def prompt_optional(label: str) -> str:
    return input(f"{label} (blank to skip): ").strip()


def prompt_choice(label: str, enum_cls, default) -> object:
    options = ", ".join(e.value for e in enum_cls)
    while True:
        raw = prompt(f"{label} ({options})", default.value)
        try:
            return enum_cls.from_str(raw)
        except ValueError as exc:
            print(f"  ! {exc}")


def prompt_due() -> Optional[datetime]:
    while True:
        raw = prompt_optional("Due date")
        if not raw:
            return None
        try:
            return parse_due(raw)
        except ValueError as exc:
            print(f"  ! {exc}")


def prompt_int(label: str) -> Optional[int]:
    raw = input(f"{label}: ").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  ! Please enter a whole number.")
        return None


def render_table(tasks: list[Task]) -> None:
    if not tasks:
        print("\n  (no tasks match)\n")
        return

    headers = ["ID", "✓", "Title", "Due", "Pri", "Recur", "Tags"]
    rows = []
    now = datetime.now()
    for t in tasks:
        mark = "✓" if t.status is Status.DONE else ("!" if t.is_overdue(now) else " ")
        rows.append(
            [
                str(t.id),
                mark,
                t.title,
                format_due(t.due),
                t.priority.value,
                t.recurrence.value if t.recurrence is not Recurrence.NONE else "—",
                ",".join(t.tags) if t.tags else "—",
            ]
        )

    widths = [
        max(len(headers[i]), max(len(r[i]) for r in rows)) for i in range(len(headers))
    ]
    line = "  " + "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print("\n" + line)
    print("  " + "  ".join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        print("  " + "  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    print(f"\n  {len(tasks)} task(s). '!' = overdue, '✓' = done.\n")

def add(repo: TaskRepository) -> None:
    print("\n— Add a task —")
    title = prompt("Title")
    if not title:
        print("  ! Title is required; aborting.")
        return
    task = Task(
        title=title,
        due=prompt_due(),
        priority=prompt_choice("Priority", Priority, Priority.MEDIUM),
        recurrence=prompt_choice("Recurrence", Recurrence, Recurrence.NONE),
        tags=[t for t in prompt_optional("Tags (comma-separated)").split(",") if t],
        notes=prompt_optional("Notes"),
    )
    if task.recurrence is not Recurrence.NONE and task.due is None:
        print("  ! Recurring tasks need a due date; setting recurrence to none.")
        task.recurrence = Recurrence.NONE
    saved = repo.add(task)
    print(f"  + Added task #{saved.id}.")


def list(repo: TaskRepository) -> None:
    print("\n— All tasks —")
    render_table(repo.list())


def filter(repo: TaskRepository) -> None:
    print("\n— Filter / search —")
    status_raw = prompt_optional("Status (pending/done)")
    priority_raw = prompt_optional("Priority (low/medium/high)")
    tag = prompt_optional("Tag") or None
    search = prompt_optional("Text search (title/notes)") or None

    try:
        status = Status.from_str(status_raw) if status_raw else None
        priority = Priority.from_str(priority_raw) if priority_raw else None
    except ValueError as exc:
        print(f"  ! {exc}")
        return

    results = repo.list(
        status=status, priority=priority, tag=tag, search=search
    )
    render_table(results)


def edit(repo: TaskRepository) -> None:
    print("\n— Edit a task —")
    task_id = prompt_int("Task ID to edit")
    if task_id is None:
        return
    task = repo.get(task_id)
    if task is None:
        print(f"  ! No task with ID {task_id}.")
        return

    print("  (blank keeps the current value)")
    new_title = prompt("Title", task.title)
    task.title = new_title

    due_raw = input(f"Due [{format_due(task.due)}] (blank keeps, '-' clears): ").strip()
    if due_raw == "-":
        task.due = None
    elif due_raw:
        try:
            task.due = parse_due(due_raw)
        except ValueError as exc:
            print(f"  ! {exc} (keeping existing date)")

    task.priority = prompt_choice("Priority", Priority, task.priority)
    task.recurrence = prompt_choice("Recurrence", Recurrence, task.recurrence)

    tags_raw = input(f"Tags [{','.join(task.tags) or '—'}] (blank keeps): ").strip()
    if tags_raw:
        task.tags = [t for t in tags_raw.split(",") if t.strip()]

    repo.update(task)
    print(f"  ~ Updated task #{task.id}.")


def complete(repo: TaskRepository) -> None:
    print("\n— Complete a task —")
    task_id = prompt_int("Task ID to complete")
    if task_id is None:
        return
    result = repo.complete(task_id)
    if result is None:
        print(f"  ! No task with ID {task_id}.")
    elif result.status is Status.PENDING:
        print(f"  ↻ Recurring task #{task_id} advanced to {format_due(result.due)}.")
    else:
        print(f"  ✓ Marked task #{task_id} done.")


def delete(repo: TaskRepository) -> None:
    print("\n— Delete a task —")
    task_id = prompt_int("Task ID to delete")
    if task_id is None:
        return
    confirm = prompt(f"Really delete #{task_id}? (y/N)", "n").lower()
    if confirm != "y":
        print("  · Cancelled.")
        return
    if repo.delete(task_id):
        print(f"  − Deleted task #{task_id}.")
    else:
        print(f"  ! No task with ID {task_id}.")


def clear_done(repo: TaskRepository) -> None:
    n = repo.clear_completed()
    print(f"\n  − Removed {n} completed task(s).")


_MENU: list[tuple[str, Callable[[TaskRepository], None]]] = [
    ("Add a task", add),
    ("List all tasks", list),
    ("Filter / search", filter),
    ("Edit a task", edit),
    ("Complete a task", complete),
    ("Delete a task", delete),
    ("Clear completed", clear_done),
]


def _print_menu() -> None:
    print("=" * 40)
    print(" TaskMaster")
    print("=" * 40)
    for i, (label, _) in enumerate(_MENU, start=1):
        print(f"  {i}. {label}")
    print("  0. Quit")


def run(conn: sqlite3.Connection) -> None:
    repo = TaskRepository(conn)
    while True:
        _print_menu()
        choice = input("\nChoose an option: ").strip()
        if choice == "0" or choice.lower() in {"q", "quit", "exit"}:
            print("Goodbye!")
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  ! Invalid choice.\n")
            continue
        _, action = _MENU[int(choice) - 1]
        try:
            action(repo)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            return
        except Exception as exc:  # noqa: BLE001 - surface errors, keep looping
            print(f"  ! Something went wrong: {exc}")
