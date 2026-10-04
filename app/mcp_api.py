import reflex as rx

import asyncio
import csv
import hashlib
import io
import json
import logging
import re
from contextlib import closing
from typing import Iterator

import pymssql
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text
from starlette.background import BackgroundTask

from app.states.connection_state import validate_connection
from app.states.query_state import (
    csv_cell,
    run_select,
    safe_database_error,
    validate_select,
)


mcp_api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def log_safe(message: str):
    e = RuntimeError(message)
    logging.exception(f"Error: {e}", exc_info=(type(e), e, None))


def unauthorized() -> HTTPException:
    return HTTPException(
        401,
        "Invalid, expired, or revoked access token.",
        headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
    )


async def token_owner(request: Request) -> str:
    header = request.headers.get("authorization", "")
    parts = header.split()
    if (
        len(parts) != 2
        or parts[0].lower() != "bearer"
        or not re.fullmatch(r"[A-Za-z0-9_-]{64}", parts[1])
    ):
        raise unauthorized()
    digest = hashlib.sha256(parts[1].encode("ascii")).hexdigest()
    try:
        async with rx.asession() as session:
            result = await session.execute(
                text(
                    "UPDATE mcp_access_tokens SET last_used_at = CURRENT_TIMESTAMP WHERE token_hash = :digest AND hash_algorithm = 'sha256' AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP) RETURNING owner_subject"
                ),
                {"digest": digest},
            )
            owner = result.scalar_one_or_none()
            await session.commit()
    except Exception:
        logging.exception("Unexpected error")
        log_safe("Access token verification unavailable.")
        raise HTTPException(
            503, "Authentication temporarily unavailable."
        ) from None
    if not isinstance(owner, str) or not owner.strip():
        raise unauthorized()
    return owner


@mcp_api.exception_handler(HTTPException)
async def safe_http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers={"Cache-Control": "no-store", **(exc.headers or {})},
    )


async def owned_rows(statement: str, owner: str, offset: int) -> list[dict]:
    try:
        async with rx.asession() as session:
            result = await session.execute(
                text(statement), {"owner": owner, "offset": offset}
            )
            return [dict(row) for row in result.mappings().all()]
    except Exception:
        logging.exception("Unexpected error")
        log_safe("Saved items could not be loaded.")
        raise HTTPException(
            503, "Saved items temporarily unavailable."
        ) from None


@mcp_api.get("/api/mcp/profiles")
async def profiles(
    owner: str = Depends(token_owner), offset: int = Query(0, ge=0, le=1000000)
):
    rows = await owned_rows(
        "SELECT id, name, host, port, database, username FROM sql_server_connection_profiles WHERE owner_subject = :owner ORDER BY id LIMIT 101 OFFSET :offset",
        owner,
        offset,
    )
    return JSONResponse(
        {
            "items": rows[:100],
            "next_offset": offset + 100 if len(rows) > 100 else None,
        },
        headers={"Cache-Control": "no-store"},
    )


@mcp_api.get("/api/mcp/queries")
async def queries(
    owner: str = Depends(token_owner), offset: int = Query(0, ge=0, le=1000000)
):
    rows = await owned_rows(
        "SELECT id, name, sql_text, connection_profile_id FROM saved_sql_queries WHERE owner_subject = :owner ORDER BY id LIMIT 101 OFFSET :offset",
        owner,
        offset,
    )
    return JSONResponse(
        {
            "items": rows[:100],
            "next_offset": offset + 100 if len(rows) > 100 else None,
        },
        headers={"Cache-Control": "no-store"},
    )


async def query_input(
    request: Request, owner: str
) -> tuple[dict[str, str | int], str, str]:
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise HTTPException(413, "Request too large.")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        logging.exception("Unexpected error")
        raise HTTPException(400, "Provide a valid JSON request.") from None
    finally:
        raw.clear()
    if not isinstance(body, dict) or set(body) - {
        "profile_id",
        "query_id",
        "sql",
        "password",
    }:
        raise HTTPException(
            400, "Only profile_id, query_id, sql, and password are accepted."
        )
    password = body.pop("password", "")
    profile_id = body.get("profile_id")
    query_id = body.get("query_id")
    sql = body.get("sql", "")
    if type(profile_id) is not int or profile_id <= 0:
        raise HTTPException(400, "A saved profile_id is required.")
    if not isinstance(password, str) or not password or len(password) > 4096:
        raise HTTPException(400, "A SQL password is required for this request.")
    if query_id is not None and (
        type(query_id) is not int or query_id <= 0 or sql
    ):
        raise HTTPException(400, "Provide either query_id or sql, not both.")
    if not isinstance(sql, str):
        raise HTTPException(400, "SQL must be text.")
    try:
        async with rx.asession() as session:
            profile_result = await session.execute(
                text(
                    "SELECT host, port, database, username FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id"
                ),
                {"owner": owner, "id": profile_id},
            )
            profile = profile_result.mappings().first()
            if profile is None:
                raise HTTPException(404, "Saved connection not found.")
            if query_id is not None:
                query_result = await session.execute(
                    text(
                        "SELECT sql_text FROM saved_sql_queries WHERE owner_subject = :owner AND id = :id"
                    ),
                    {"owner": owner, "id": query_id},
                )
                saved_sql = query_result.scalar_one_or_none()
                if saved_sql is None:
                    raise HTTPException(404, "Saved query not found.")
                sql = str(saved_sql)
        return (
            validate_connection(dict(profile)),
            password,
            validate_select(sql),
        )
    except HTTPException:
        logging.exception("Unexpected error")
        raise
    except ValueError:
        raise HTTPException(
            400,
            "Query rejected by the read-only guard or saved connection invalid. Use one supported SELECT.",
        ) from None
    except Exception:
        logging.exception("Unexpected error")
        log_safe("Saved query lookup failed.")
        raise HTTPException(
            503, "Saved items temporarily unavailable."
        ) from None
    finally:
        body.clear()
        password = ""


@mcp_api.post("/api/mcp/run")
async def run(request: Request, owner: str = Depends(token_owner)):
    details, password, sql = await query_input(request, owner)
    try:
        columns, rows, capped = await asyncio.to_thread(
            run_select,
            details["host"],
            int(details["port"]),
            details["database"],
            details["username"],
            password,
            sql,
        )
        return JSONResponse(
            {
                "columns": columns,
                "rows": rows,
                "capped": capped,
                "preview_limit": 200,
                "column_limit": 100,
                "cell_character_limit": 2000,
            },
            headers={"Cache-Control": "no-store"},
        )
    except (ValueError, RuntimeError):
        logging.exception("Unexpected error")
        raise HTTPException(
            400,
            "Query could not complete. Check SQL syntax, read-only permissions, credentials, connectivity, and timeouts.",
        ) from None
    except Exception:
        logging.exception("Unexpected error")
        log_safe("Query execution failed.")
        raise HTTPException(503, "Query execution unavailable.") from None
    finally:
        password = ""


def csv_stream(
    details: dict[str, str | int], password: str, sql: str
) -> Iterator[bytes]:
    stage = "connect"
    try:
        with closing(
            pymssql.connect(
                server=str(details["host"]),
                port=str(details["port"]),
                database=str(details["database"]),
                user=str(details["username"]),
                password=password,
                login_timeout=8,
                timeout=20,
                autocommit=False,
                charset="UTF-8",
                appname="SQL Workbench MCP",
            )
        ) as connection:
            password = ""
            stage = "query"
            try:
                with closing(connection.cursor()) as cursor:
                    cursor.execute("SET LOCK_TIMEOUT 5000; SET ROWCOUNT 0;")
                    cursor.execute(validate_select(sql))
                    if cursor.description is None:
                        raise ValueError("No tabular result.")
                    output = io.StringIO(newline="")
                    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
                    writer.writerow(
                        [
                            csv_cell(item[0] or f"Column {i + 1}")
                            for i, item in enumerate(cursor.description)
                        ]
                    )
                    yield f"\ufeff{output.getvalue()}".encode("utf-8")
                    while True:
                        batch = cursor.fetchmany(1000)
                        if not batch:
                            break
                        output.seek(0)
                        output.truncate(0)
                        writer.writerows(
                            [
                                [csv_cell(value) for value in row]
                                for row in batch
                            ]
                        )
                        yield output.getvalue().encode("utf-8")
            finally:
                connection.rollback()
    except Exception as original:
        e = RuntimeError(safe_database_error(original, stage))
        logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
        raise e from None
    finally:
        password = ""


def complete_stream(first: bytes, stream: Iterator[bytes]) -> Iterator[bytes]:
    try:
        yield first
        yield from stream
    finally:
        stream.close()


@mcp_api.post("/api/mcp/export")
async def export(request: Request, owner: str = Depends(token_owner)):
    details, password, sql = await query_input(request, owner)
    stream = csv_stream(details, password, sql)
    password = ""
    try:
        first = await asyncio.to_thread(next, stream)
    except Exception:
        logging.exception("Unexpected error")
        await asyncio.to_thread(stream.close)
        raise HTTPException(
            400,
            "CSV query could not start. Check credentials, connectivity, SQL, and permissions.",
        ) from None
    return StreamingResponse(
        complete_stream(first, stream),
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="query-results.csv"',
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(stream.close),
    )
