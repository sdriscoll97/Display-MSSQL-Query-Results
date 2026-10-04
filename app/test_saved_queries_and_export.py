import reflex as rx

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.states.query_state import csv_cell, export_select


class CSVExportTests(unittest.TestCase):
    def test_formula_safety(self):
        for value in (
            "=SUM(A1:A2)",
            "+cmd",
            "-cmd",
            "@cmd",
            "  =1",
            "\t=1",
            "\n=1",
        ):
            self.assertTrue(csv_cell(value).startswith("'"))
        self.assertEqual(csv_cell(None), "")
        self.assertEqual(csv_cell(b"\x00\xff"), "0x00ff")
        self.assertEqual(
            csv_cell('text, "quoted"\nsecond line'),
            'text, "quoted"\nsecond line',
        )

    @patch("app.states.query_state.pymssql.connect")
    def test_full_stream_no_preview_truncation(self, connect: MagicMock):
        connection = connect.return_value
        cursor = connection.cursor.return_value
        cursor.description = [("=header",), ("notes",)]
        long_value = 'long, "quoted"\n' * 300
        cursor.fetchmany.side_effect = [
            [(index, long_value) for index in range(1000)],
            [(index, "=1+1") for index in range(1000, 1357)],
            [],
        ]
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.csv"
            count = export_select(
                "host",
                1433,
                "db",
                "reader",
                "password",
                "SELECT id, notes FROM dbo.items",
                path,
                progress.append,
            )
            with path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file))
        self.assertEqual(count, 1357)
        self.assertEqual(len(rows), 1358)
        self.assertEqual(rows[0][0], "'=header")
        self.assertEqual(rows[1][1], long_value)
        self.assertEqual(rows[-1][1], "'=1+1")
        self.assertEqual(progress, [1000, 1357])
        self.assertEqual(
            cursor.execute.call_args_list[0].args[0],
            "SET LOCK_TIMEOUT 5000; SET ROWCOUNT 0;",
        )
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        cursor.close.assert_called_once()

    @patch("app.states.query_state.pymssql.connect")
    def test_invalid_export_never_connects(self, connect: MagicMock):
        with self.assertRaises(ValueError):
            export_select(
                "host",
                1433,
                "db",
                "reader",
                "password",
                "DELETE FROM dbo.items",
                Path("unused.csv"),
                lambda count: None,
            )
        connect.assert_not_called()

    @patch("app.states.query_state.pymssql.connect")
    def test_stream_failure_not_success(self, connect: MagicMock):
        cursor = connect.return_value.cursor.return_value
        cursor.description = [("value",)]
        cursor.fetchmany.side_effect = [
            [(1,)],
            Exception("secret password timeout"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                export_select(
                    "host",
                    1433,
                    "db",
                    "reader",
                    "password",
                    "SELECT 1",
                    Path(directory) / "partial.csv",
                    lambda count: None,
                )
        connect.return_value.rollback.assert_called_once()


class SavedQueryScopeTests(unittest.TestCase):
    def test_all_saved_query_statements_bind_owner(self):
        source = (
            Path(__file__)
            .parent.joinpath("states", "saved_query_state.py")
            .read_text()
        )
        statements = [
            line
            for line in source.splitlines()
            if 'text("' in line and "saved_sql_queries" in line
        ]
        self.assertEqual(len(statements), 5)
        for statement in statements:
            self.assertIn(":owner", statement)
            self.assertNotIn("password", statement)
        self.assertIn("FOR KEY SHARE", source)
        self.assertIn("validate_select(sql)", source)

    def test_save_capture_excludes_password_and_owner(self):
        source = (
            Path(__file__)
            .parent.joinpath("components", "saved_queries.py")
            .read_text()
        )
        capture = next(
            line
            for line in source.splitlines()
            if line.startswith("SAVE_QUERY_SCRIPT")
        )
        self.assertNotIn("password", capture)
        self.assertNotIn("owner", capture)
