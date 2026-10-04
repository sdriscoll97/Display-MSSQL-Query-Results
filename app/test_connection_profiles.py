import reflex as rx

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.states.connection_state import current_subject, validate_connection


class ConnectionValidationTests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "name": "Reporting",
            "host": "sql.example.com",
            "port": "1433",
            "database": "Reports",
            "username": "reader",
        }

    def test_valid_profile(self):
        result = validate_connection(self.fields, named=True)
        self.assertEqual(result["port"], 1433)
        self.assertEqual(result["name"], "Reporting")
        self.assertNotIn("password", result)
        self.assertNotIn("owner_subject", result)

    def test_secrets_and_owner_are_discarded(self):
        result = validate_connection(
            {
                **self.fields,
                "password": "not-retained",
                "owner_subject": "forged",
            },
            named=True,
        )
        self.assertEqual(
            set(result), {"name", "host", "port", "database", "username"}
        )

    def test_invalid_fields(self):
        for field, value in (
            ("name", " "),
            ("name", "x" * 201),
            ("host", "https://sql.example.com"),
            ("host", "sql.example.com,1433"),
            ("host", "server\nother"),
            ("database", "x" * 129),
            ("username", ""),
            ("port", "0"),
            ("port", "65536"),
            ("port", "abc"),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    validate_connection(
                        {**self.fields, field: value}, named=True
                    )

    def test_ad_hoc_does_not_require_name(self):
        self.fields.pop("name")
        self.assertEqual(
            validate_connection(self.fields)["host"], "sql.example.com"
        )

    def test_every_profile_statement_has_owner_scope(self):
        source = (
            Path(__file__)
            .parent.joinpath("states", "connection_state.py")
            .read_text()
        )
        statements = [
            line
            for line in source.splitlines()
            if "text(" in line and "sql_server_connection_profiles" in line
        ]
        self.assertEqual(len(statements), 5)
        for statement in statements:
            self.assertIn("owner", statement)
            self.assertIn(":owner", statement)
            self.assertNotIn("password", statement)

    def test_password_not_in_profile_capture(self):
        source = (
            Path(__file__)
            .parent.joinpath("components", "connection_manager.py")
            .read_text()
        )
        script = next(
            line for line in source.splitlines() if "Object.fromEntries" in line
        )
        self.assertNotIn("password", script)


class SubjectTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.states.connection_state.User.current", new_callable=AsyncMock)
    async def test_stable_subject(self, current):
        current.return_value = {
            "sub": "stable-subject",
            "email": "changeable@example.com",
        }
        self.assertEqual(await current_subject(), "stable-subject")

    @patch("app.states.connection_state.User.current", new_callable=AsyncMock)
    async def test_anonymous_fails_closed(self, current):
        current.return_value = None
        with self.assertRaises(ValueError):
            await current_subject()
