import reflex as rx

import asyncio
import csv
import hashlib
import io
import secrets
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from starlette.requests import Request

from app.mcp_api import csv_stream, mcp_api, query_input, token_owner
from app.claude_desktop_mcp import settings, payload


class APITests(unittest.IsolatedAsyncioTestCase):
    async def test_all_routes_deny_anonymous(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mcp_api),
            base_url="https://workbench.test",
        ) as client:
            for method, path in [
                ("GET", "profiles"),
                ("GET", "queries"),
                ("POST", "run"),
                ("POST", "export"),
            ]:
                response = await client.request(method, f"/api/mcp/{path}")
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")

    async def test_hash_lookup_derives_owner_and_enforces_lifecycle(self):
        token = secrets.token_urlsafe(48)
        request = Request(
            {
                "type": "http",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
            }
        )
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = "server-owner"
        session.execute.return_value = result
        manager = AsyncMock()
        manager.__aenter__.return_value = session
        with patch("app.mcp_api.rx.asession", return_value=manager):
            self.assertEqual(await token_owner(request), "server-owner")
            statement, params = session.execute.call_args.args
            self.assertEqual(
                params, {"digest": hashlib.sha256(token.encode()).hexdigest()}
            )
            self.assertIn("revoked_at IS NULL", str(statement))
            self.assertIn("expires_at > CURRENT_TIMESTAMP", str(statement))
            self.assertNotIn(token, str(statement))
            result.scalar_one_or_none.return_value = None
            with self.assertRaises(HTTPException) as error:
                await token_owner(request)
            self.assertEqual(error.exception.status_code, 401)

    async def test_other_owner_profile_returns_404(self):
        import json

        data = json.dumps(
            {"profile_id": 1, "sql": "SELECT 1", "password": "private"}
        ).encode()
        receive = AsyncMock(
            return_value={
                "type": "http.request",
                "body": data,
                "more_body": False,
            }
        )
        request = Request({"type": "http", "headers": []}, receive)
        session = AsyncMock()
        result = MagicMock()
        result.mappings.return_value.first.return_value = None
        session.execute.return_value = result
        manager = AsyncMock()
        manager.__aenter__.return_value = session
        with patch("app.mcp_api.rx.asession", return_value=manager):
            with self.assertRaises(HTTPException) as error:
                await query_input(request, "owner-from-token")
            self.assertEqual(error.exception.status_code, 404)
            statement, params = session.execute.call_args.args
            self.assertIn("owner_subject = :owner", str(statement))
            self.assertEqual(params["owner"], "owner-from-token")

    async def test_forged_owner_rejected(self):
        receive = AsyncMock(
            return_value={
                "type": "http.request",
                "body": b'{"owner_subject":"forged"}',
                "more_body": False,
            }
        )
        request = Request({"type": "http", "headers": []}, receive)
        with self.assertRaises(HTTPException) as error:
            await query_input(request, "real-owner")
        self.assertEqual(error.exception.status_code, 400)


class StreamTests(unittest.TestCase):
    @patch("app.mcp_api.pymssql.connect")
    def test_csv_all_rows_formula_safety_and_cleanup(self, connect):
        cursor = connect.return_value.cursor.return_value
        cursor.description = [("=header",)]
        cursor.fetchmany.side_effect = [
            [("x" * 3000,)] * 1000,
            [("=1",)] * 357,
            [],
        ]
        stream = csv_stream(
            {
                "host": "server",
                "port": 1433,
                "database": "db",
                "username": "reader",
            },
            "private",
            "SELECT 1",
        )
        content = b"".join(stream).decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(len(rows), 1358)
        self.assertEqual(rows[0][0], "'=header")
        self.assertEqual(len(rows[1][0]), 3000)
        self.assertEqual(rows[-1][0], "'=1")
        self.assertIn(
            "SET ROWCOUNT 0", cursor.execute.call_args_list[0].args[0]
        )
        connect.return_value.rollback.assert_called_once()
        connect.return_value.close.assert_called_once()

    @patch("app.mcp_api.pymssql.connect")
    def test_stream_failure_is_not_success_and_hides_driver_error(
        self, connect
    ):
        cursor = connect.return_value.cursor.return_value
        cursor.description = [("value",)]
        cursor.fetchmany.side_effect = RuntimeError("password=private")
        with self.assertRaises(RuntimeError) as error:
            b"".join(
                csv_stream(
                    {
                        "host": "s",
                        "port": 1433,
                        "database": "d",
                        "username": "r",
                    },
                    "private",
                    "SELECT 1",
                )
            )
        self.assertNotIn("private", str(error.exception))
        connect.return_value.close.assert_called_once()


class LocalSettingsTests(unittest.TestCase):
    def test_https_required_and_password_not_a_tool_argument(self):
        from mcp.server.fastmcp.exceptions import ToolError

        env = {
            "WORKBENCH_API_URL": "http://remote.example",
            "WORKBENCH_API_TOKEN": "a" * 64,
        }
        with patch.dict("os.environ", env):
            with self.assertRaises(ToolError):
                settings()
        env.update(
            {
                "WORKBENCH_API_URL": "http://localhost:8000",
                "WORKBENCH_SQL_PASSWORDS_JSON": '{"12":"local-only"}',
            }
        )
        with patch.dict("os.environ", env):
            self.assertEqual(
                payload(12, "SELECT 1", 0)["password"], "local-only"
            )
        import inspect
        from app.claude_desktop_mcp import run_read_only_query, export_csv

        self.assertNotIn(
            "password", inspect.signature(run_read_only_query).parameters
        )
        self.assertNotIn("password", inspect.signature(export_csv).parameters)


if __name__ == "__main__":
    unittest.main()
