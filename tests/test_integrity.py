"""Regression checks for database atomicity and frontend syntax."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import subprocess
import shutil

from app import main


def test_database_rolls_back_failed_operation():
    with TemporaryDirectory() as folder:
        original=main.DB
        try:
            main.DB=Path(folder)/"rollback.db"
            with main.database() as db:
                db.execute("CREATE TABLE items (name TEXT)")
            try:
                with main.database() as db:
                    db.execute("INSERT INTO items(name) VALUES('partial')")
                    raise ValueError("simulate failure")
            except ValueError:
                pass
            with main.database() as db:
                assert db.execute("SELECT count(*) FROM items").fetchone()[0]==0
        finally:
            main.DB=original


def test_frontend_javascript_syntax():
    node=shutil.which("node")
    if not node:
        import pytest
        pytest.skip("Node.js is unavailable")
    root=Path(__file__).resolve().parents[1]
    html=(root/"web/index.html").read_text(encoding="utf-8")
    script=html.split("<script>",1)[1].split("</script>",1)[0]
    with TemporaryDirectory() as folder:
        inline=Path(folder)/"inline.js"
        inline.write_text(script,encoding="utf-8")
        for path in (inline,root/"web/development.js",root/"web/career.js",root/"web/overview.js"):
            subprocess.run([node,"--check",str(path)],check=True,capture_output=True,text=True)
