# TaskMaster

Repository to demonstrate the functionality of taskmaster, a simple application with CRUD functionalities that satisfy the needs of a user for scheduling needs.

# Features
- Create (add), Read(list) , Update(edit), Delete
- Recurring Tasks | Choice for daily/weekly/monthly/yearly tasks (If value is null means non-recurring task). When a recurring task is completed, it automatically rolls the date forward to next occurence without closing the instance.
- Priorities | Mark tasks as low/medium/high priority based on severity.
- Searching | List tasks based on filter, can be based on status, priority, a tag or just the title or note content.
- Date Format | Keywords like "Tomorrow 5:40pm" or "06-04-2026 17:40" work just fine.
- Overdue date marking | Pending tasks past their due date are flagged.
- Local Data Storing | Using SQLite in Python everything lives inside the machine running it.

# Requirements
Python 3.10 or newer (Testing version ran on 3.10 and 3.14.5)

Recommended but not required: Dateparser for natural-language dates, otherwise it runs on strict date formats.
