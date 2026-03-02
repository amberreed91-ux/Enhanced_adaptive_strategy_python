from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory


def init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT, done INTEGER)')


def add_task(db_path: Path, title: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute('INSERT INTO tasks (title, done) VALUES (?, 0)', (title,))
        return int(cur.lastrowid)


def list_tasks(db_path: Path) -> list[tuple[int, str, int]]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute('SELECT id, title, done FROM tasks ORDER BY id').fetchall()


def run_demo() -> dict[str, object]:
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / 'portfolio_tasks.db'
        init_db(db_path)
        add_task(db_path, 'ship portfolio app')
        tasks = list_tasks(db_path)
        return {'project': 'task_manager_webapp', 'tasks': len(tasks)}


if __name__ == '__main__':
    print(run_demo())
