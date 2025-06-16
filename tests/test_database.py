import ast
import sqlite3
import textwrap
from pathlib import Path


def get_create_table_sql(path: Path) -> str:
    src = path.read_text()
    module = ast.parse(src)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "create_users_table",
                    "CREATE_USERS_TABLE_SQL",
                ):
                    if (
                        isinstance(node.value, ast.Call)
                        and getattr(node.value.func, "attr", "") == "dedent"
                    ):
                        arg = node.value.args[0]
                        if isinstance(arg, ast.Constant):
                            return textwrap.dedent(arg.value)
    raise RuntimeError("users table SQL definition not found")


def test_create_users_table_sql_valid():
    sql = get_create_table_sql(Path("main.py"))
    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.execute(sql)  # should not raise
    # verify table schema includes group_personas column
    cur.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cur.fetchall()]
    assert "group_personas" in cols
