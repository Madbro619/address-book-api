"""Small SQLite repository with explicit transactions and parameterized SQL."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    street TEXT NOT NULL CHECK(length(trim(street)) BETWEEN 1 AND 200),
    city TEXT NOT NULL CHECK(length(trim(city)) BETWEEN 1 AND 200),
    country TEXT NOT NULL CHECK(length(trim(country)) BETWEEN 1 AND 200),
    postal_code TEXT NOT NULL CHECK(length(trim(postal_code)) BETWEEN 1 AND 32),
    latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180)
);
"""
COLUMNS = ("street", "city", "country", "postal_code", "latitude", "longitude")


class AddressRepository:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connection(self):
        # Each operation opens and closes its own connection in the worker thread.
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    def create(self, data: dict) -> dict:
        with self.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO addresses (street, city, country, postal_code, latitude, longitude) "
                "VALUES (?, ?, ?, ?, ?, ?)", tuple(data[key] for key in COLUMNS)
            )
            return dict(conn.execute("SELECT * FROM addresses WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def get(self, address_id: int) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM addresses WHERE id = ?", (address_id,)).fetchone()
            return dict(row) if row else None

    def list_addresses(self, limit: int, offset: int) -> list[dict]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM addresses ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            )]

    def all(self) -> list[dict]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM addresses ORDER BY id")]

    def update(self, address_id: int, changes: dict) -> dict | None:
        # Column names come exclusively from this fixed allowlist; values are bound.
        fields = [key for key in COLUMNS if key in changes]
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self.connection() as conn:
            cursor = conn.execute(
                f"UPDATE addresses SET {assignments} WHERE id = ?",
                (*[changes[key] for key in fields], address_id),
            )
            if cursor.rowcount == 0:
                return None
            return dict(conn.execute("SELECT * FROM addresses WHERE id = ?", (address_id,)).fetchone())

    def delete(self, address_id: int) -> bool:
        with self.connection() as conn:
            return conn.execute("DELETE FROM addresses WHERE id = ?", (address_id,)).rowcount > 0
