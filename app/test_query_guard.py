import reflex as rx

import unittest
from unittest.mock import MagicMock, patch

from app.states.query_state import (
    EXAMPLE_SQL,
    run_select,
    safe_database_error,
    validate_select,
)


class QueryGuardTests(unittest.TestCase):
    def test_selects(self):
        for sql in (
            EXAMPLE_SQL,
            "SELECT 1;",
            "-- hello\nSELECT 'DROP; TABLE' AS note;",
            "SELECT [update] FROM [table]",
            "SELECT COUNT(*) FROM dbo.orders",
            "SELECT 1 UNION ALL SELECT 2",
            "SELECT name FROM dbo.orders WHERE id IN (SELECT id FROM dbo.items)",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(validate_select(sql))

    def test_rejected_queries(self):
        for sql in (
            "",
            "DELETE FROM dbo.orders",
            "SELECT 1; SELECT 2",
            "SELECT 1 SELECT 2",
            "SELECT * INTO dbo.copy FROM dbo.orders",
            "SELECT * FROM OPENROWSET('x')",
            "SELECT dbo.side_effect()",
            "SELECT NEXT VALUE FOR dbo.sequence",
            "SELECT * FROM server.db.dbo.orders",
            "SELECT * FROM dbo.orders WITH (UPDLOCK)",
            "WITH x AS (SELECT 1) SELECT * FROM x",
            "SELECT 'unclosed",
            "SELECT 1 /* unclosed",
            "SELECT 1; DROP TABLE dbo.orders",
            "SELECT 1 /* outer /* inner */ */",
        ):
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    validate_select(sql)

    def test_error_redaction(self):
        message = safe_database_error(
            Exception("secret-password host secret-host login failed 18456"),
            "connect",
        )
        self.assertIn("Login failed", message)
        self.assertNotIn("secret", message)

    @patch("app.states.query_state.pymssql.connect")
    def test_cap_rollback_and_close(self, connect: MagicMock):
        connection = connect.return_value
        cursor = connection.cursor.return_value
        cursor.description = [("value",)]
        cursor.fetchmany.return_value = [(number,) for number in range(201)]
        columns, rows, capped = run_select(
            "host",
            1433,
            "db",
            "user",
            "password",
            "SELECT value FROM dbo.items",
        )
        self.assertEqual(columns, ["value"])
        self.assertEqual(len(rows), 200)
        self.assertTrue(capped)
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        cursor.close.assert_called_once()
        self.assertEqual(connect.call_args.kwargs["timeout"], 20)
        self.assertEqual(connect.call_args.kwargs["login_timeout"], 8)

    @patch("app.states.query_state.pymssql.connect")
    def test_empty_results(self, connect: MagicMock):
        cursor = connect.return_value.cursor.return_value
        cursor.description = [("name",)]
        cursor.fetchmany.return_value = []
        columns, rows, capped = run_select(
            "host", 1433, "db", "user", "password", "SELECT name FROM dbo.items"
        )
        self.assertEqual(columns, ["name"])
        self.assertEqual(rows, [])
        self.assertFalse(capped)
