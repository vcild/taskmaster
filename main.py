from __future__ import annotations
import sys
from taskmaster import __version__
from taskmaster.cli import run
from taskmaster.db import get_connection, resolve_db_path


def main() -> int:
    if "--version" in sys.argv:
        print(f"TaskMaster {__version__}")
        return 0

    print(f"TaskMaster {__version__} — database: {resolve_db_path()}")
    conn = get_connection()
    try:
        run(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
