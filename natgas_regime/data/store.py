from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd


class DuckDBStore:
    """Small DuckDB wrapper used as the local source of truth."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    def write_frame(self, table: str, frame: pd.DataFrame) -> None:
        with self.connect() as con:
            con.register("_frame", frame)
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _frame")
            con.unregister("_frame")

    def read_frame(self, table: str) -> pd.DataFrame:
        with self.connect() as con:
            return con.execute(f"SELECT * FROM {table}").fetchdf()

    def has_table(self, table: str) -> bool:
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_name = ?
                """,
                [table],
            ).fetchall()
        return bool(rows)

