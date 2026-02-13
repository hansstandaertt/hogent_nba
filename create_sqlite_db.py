from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mock_db.sqlite3"


def _load_json(file_path: Path) -> list[dict[str, Any]]:
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected list in {file_path}, got {type(raw).__name__}")
    return raw


def _to_int_bool(value: Any) -> int:
    return 1 if bool(value) else 0


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS client_products;
        DROP TABLE IF EXISTS client_employees;
        DROP TABLE IF EXISTS clients;
        DROP TABLE IF EXISTS clients;

        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            enterprise_number TEXT NOT NULL,
            account_id TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            city TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            amount REAL NOT NULL,
            date_created TEXT NOT NULL,
            date_paid TEXT,
            is_paid INTEGER NOT NULL CHECK (is_paid IN (0, 1)),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE TABLE client_products (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
            employee_id TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE TABLE client_employees (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT NOT NULL,
            monthly_income REAL NOT NULL,
            is_primary_contact INTEGER NOT NULL CHECK (is_primary_contact IN (0, 1)),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def import_data(conn: sqlite3.Connection, data_dir: Path) -> dict[str, int]:
    clients = _load_json(data_dir / "clients.json")
    invoices = _load_json(data_dir / "invoices.json")
    client_products = _load_json(data_dir / "client_products.json")
    client_employees = _load_json(data_dir / "client_employees.json")

    with conn:
        conn.executemany(
            """
            INSERT INTO clients (
                id, enterprise_number, account_id, first_name, last_name,
                email, phone, city, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["enterprise_number"],
                    row["account_id"],
                    row["first_name"],
                    row["last_name"],
                    row["email"],
                    row["phone"],
                    row["city"],
                    row["created_at"],
                )
                for row in clients
            ],
        )

        conn.executemany(
            """
            INSERT INTO invoices (id, client_id, amount, date_created, date_paid, is_paid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["client_id"],
                    row["amount"],
                    row["date_created"],
                    row.get("date_paid"),
                    _to_int_bool(row["is_paid"]),
                )
                for row in invoices
            ],
        )

        conn.executemany(
            """
            INSERT INTO client_products (
                id, client_id, product_id, product_name, start_date, end_date, is_active, employee_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["client_id"],
                    row["product_id"],
                    row["product_name"],
                    row["start_date"],
                    row.get("end_date"),
                    _to_int_bool(row["is_active"]),
                    row.get("employee_id"),
                )
                for row in client_products
            ],
        )

        conn.executemany(
            """
            INSERT INTO client_employees (
                id, client_id, first_name, last_name, email, role,
                department, monthly_income, is_primary_contact
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["client_id"],
                    row["first_name"],
                    row["last_name"],
                    row["email"],
                    row["role"],
                    row["department"],
                    row["monthly_income"],
                    _to_int_bool(row["is_primary_contact"]),
                )
                for row in client_employees
            ],
        )

    return {
        "clients": len(clients),
        "invoices": len(invoices),
        "client_products": len(client_products),
        "client_employees": len(client_employees),
    }


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        create_schema(conn)
        counts = import_data(conn, BASE_DIR / "mock_db")

    print(f"SQLite database created at: {DB_PATH}")
    for table_name, count in counts.items():
        print(f"{table_name}: {count} rows imported")


if __name__ == "__main__":
    main()
