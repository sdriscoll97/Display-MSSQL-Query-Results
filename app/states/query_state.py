import reflex as rx

import asyncio
import csv
import queue
import secrets
from pathlib import Path
import logging
import re
import time
from contextlib import closing
from typing import Any, Callable

import pymssql
import reflex_enterprise as rxe
from sqlalchemy import text

from app.states.connection_state import (
    ConnectionState,
    current_subject,
    validate_connection,
)


EXAMPLE_SQL = "SELECT TOP (50)\n    TABLE_SCHEMA,\n    TABLE_NAME,\n    TABLE_TYPE\nFROM INFORMATION_SCHEMA.TABLES\nORDER BY TABLE_SCHEMA, TABLE_NAME;"
ROW_LIMIT = 200
TOKEN = re.compile(
    r"\s+|--[^\n]*|/\*.*?\*/|'(?:''|[^'])*'|\[(?:\]\]|[^\]])*\]|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+(?:\.[0-9]+)?|[(),.;+*/%=<>!~-]",
    re.S,
)
FORBIDDEN = set(
    "INSERT UPDATE DELETE MERGE INTO EXEC EXECUTE CREATE ALTER DROP TRUNCATE GRANT REVOKE DENY BACKUP RESTORE DBCC USE SET DECLARE PRINT RAISERROR THROW WAITFOR KILL SHUTDOWN RECONFIGURE BULK OPENROWSET OPENQUERY OPENDATASOURCE OPENXML NEXT VALUE FOR GO COMMIT ROLLBACK BEGIN END TRANSACTION OUTPUT UPDLOCK XLOCK TABLOCKX HOLDLOCK READPAST OPTION SERVICE BROKER SEND RECEIVE".split()
)
FUNCTIONS = set(
    "TOP COUNT COUNT_BIG SUM AVG MIN MAX ABS ROUND FLOOR CEILING LEN DATALENGTH LOWER UPPER LTRIM RTRIM TRIM CONCAT CONCAT_WS SUBSTRING LEFT RIGHT REPLACE REPLICATE REVERSE CHARINDEX PATINDEX COALESCE ISNULL NULLIF CAST CONVERT TRY_CAST TRY_CONVERT DATEADD DATEDIFF DATEDIFF_BIG DATEPART DATENAME YEAR MONTH DAY GETDATE GETUTCDATE SYSDATETIME SYSUTCDATETIME CURRENT_TIMESTAMP ROW_NUMBER RANK DENSE_RANK NTILE LEAD LAG FIRST_VALUE LAST_VALUE IIF CHOOSE STRING_AGG FORMAT OVER IN EXISTS NOT AS".split()
)


def validate_select(sql: str) -> str:
    if not sql.strip():
        raise ValueError("Enter a SELECT query before executing.")
    if len(sql) > 20000:
        raise ValueError("Keep the query under 20,000 characters.")
    tokens: list[str] = []
    position = 0
    for match in TOKEN.finditer(sql):
        if match.start() != position:
            raise ValueError(
                "Unsupported SQL syntax. Use a plain SELECT with standard identifiers and expressions."
            )
        position = match.end()
        token = match.group()
        if token.isspace() or token.startswith("--"):
            continue
        if token.startswith("/*"):
            if "/*" in token[2:]:
                raise ValueError("Nested block comments are not supported.")
            continue
        tokens.append(token)
    if position != len(sql):
        raise ValueError(
            "Check for an unclosed quote, comment, or unsupported SQL character."
        )
    if tokens and tokens[-1] == ";":
        tokens.pop()
    if not tokens or tokens[0].upper() != "SELECT":
        raise ValueError(
            "Only a single SELECT is allowed. CTEs, stored procedures, and other statements are not supported."
        )
    if ";" in tokens:
        raise ValueError(
            "Multiple statements are not allowed. Use only one SELECT with an optional final semicolon."
        )
    depth = 0
    for index, token in enumerate(tokens):
        upper = token.upper()
        if upper in FORBIDDEN:
            raise ValueError(f"Read-only guard: {upper} is not permitted.")
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("Check the query's parentheses.")
        elif upper == "SELECT" and index > 0 and depth == 0:
            previous = tokens[index - 1].upper()
            union_all = (
                previous == "ALL"
                and index > 1
                and tokens[index - 2].upper() == "UNION"
            )
            if (
                previous not in {"UNION", "EXCEPT", "INTERSECT"}
                and not union_all
            ):
                raise ValueError(
                    "Multiple SELECT statements are not allowed. Submit one result-producing query."
                )
        if (
            index + 1 < len(tokens)
            and tokens[index + 1] == "("
            and (token[0].isalpha() or token.startswith(("[", '"')))
        ):
            if upper not in FUNCTIONS or (
                index > 0 and tokens[index - 1] == "."
            ):
                raise ValueError(
                    "Only supported built-in functions are allowed; custom and remote functions are blocked."
                )
    if depth:
        raise ValueError("Check the query's parentheses.")
    normalized = " ".join(tokens)
    if re.search(r"(?:[^\s.]+\s*\.\s*){3}", normalized):
        raise ValueError(
            "Linked-server / four-part object names are not allowed. Query the selected database locally."
        )
    return normalized


def safe_database_error(error: Exception, stage: str) -> str:
    details = str(error).lower()
    if "18456" in details or "login failed" in details:
        return "Login failed. Verify the username and password and confirm SQL Server authentication is enabled."
    if "4060" in details or "cannot open database" in details:
        return "The database could not be opened. Check its name and the user's access permissions."
    if "timeout" in details or "timed out" in details:
        return "The operation timed out. Check server connectivity or simplify the query. Login timeout: 8s; query timeout: 20s."
    if "208" in details or "invalid object" in details:
        return "The query references an object that was not found. Check the database, schema, and table name."
    if "207" in details or "invalid column" in details:
        return "A column was not found. Check column names against the selected database's schema."
    if "229" in details or "permission" in details:
        return "Permission denied. Ask your database administrator for SELECT access to the required objects."
    if "syntax" in details or "102," in details or "156," in details:
        return "SQL Server rejected the query syntax. Check identifiers, expressions, and T-SQL syntax."
    if stage == "connect":
        return "Could not connect to SQL Server. Verify the host, TCP port, network access, and SQL Server protocol. This driver does not support other database engines."
    return "The query could not be completed. Check T-SQL syntax, object permissions, and server availability. Raw driver messages are hidden to protect credentials."


def run_select(
    host: str, port: int, database: str, username: str, password: str, sql: str
) -> tuple[list[str], list[list[str]], bool]:
    stage = "connect"
    try:
        with closing(
            pymssql.connect(
                server=host,
                port=str(port),
                database=database,
                user=username,
                password=password,
                login_timeout=8,
                timeout=20,
                autocommit=False,
                charset="UTF-8",
                appname="SQL Workbench",
            )
        ) as connection:
            password = ""
            stage = "query"
            try:
                with closing(connection.cursor()) as cursor:
                    cursor.execute("SET LOCK_TIMEOUT 5000; SET ROWCOUNT 201;")
                    cursor.execute(sql)
                    if cursor.description is None:
                        raise ValueError(
                            "The SELECT did not return a tabular result."
                        )
                    columns = [
                        str(item[0] or f"Column {index + 1}")
                        for index, item in enumerate(cursor.description)
                    ]
                    if len(columns) > 100:
                        raise ValueError(
                            "This query returns more than 100 columns. Select fewer columns for a readable result."
                        )
                    fetched = cursor.fetchmany(ROW_LIMIT + 1)
                    rows = []
                    for row in fetched[:ROW_LIMIT]:
                        cells = []
                        for value in row:
                            text = (
                                "NULL"
                                if value is None
                                else (
                                    f"0x{value[:512].hex()}"
                                    if isinstance(value, bytes)
                                    else str(value)
                                )
                            )
                            cells.append(
                                f"{text[:2000]} … [truncated]"
                                if len(text) > 2000
                                else text
                            )
                        rows.append(cells)
                    return columns, rows, len(fetched) > ROW_LIMIT
            finally:
                connection.rollback()
    except ValueError:
        raise
    except Exception as original:
        e = RuntimeError(safe_database_error(original, stage))
        logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
        raise e from None
    finally:
        password = ""


def csv_cell(value: object) -> str:
    if value is None:
        return ""
    result = f"0x{value.hex()}" if isinstance(value, bytes) else str(value)
    if result.lstrip(" \t\r\n\ufeff").startswith(
        ("=", "+", "-", "@")
    ) or result.startswith(("\t", "\r", "\n")):
        return f"'{result}"
    return result


def export_select(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    sql: str,
    path: Path,
    progress: Callable[[int], None],
) -> int:
    stage = "connect"
    try:
        sql = validate_select(sql)
        with closing(
            pymssql.connect(
                server=host,
                port=str(port),
                database=database,
                user=username,
                password=password,
                login_timeout=8,
                timeout=20,
                autocommit=False,
                charset="UTF-8",
                appname="SQL Workbench CSV",
            )
        ) as connection:
            password = ""
            stage = "query"
            try:
                with closing(connection.cursor()) as cursor:
                    cursor.execute("SET LOCK_TIMEOUT 5000; SET ROWCOUNT 0;")
                    cursor.execute(sql)
                    if cursor.description is None:
                        raise ValueError(
                            "The SELECT did not return a tabular result."
                        )
                    with path.open(
                        "w", encoding="utf-8-sig", newline=""
                    ) as output:
                        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
                        writer.writerow(
                            [
                                csv_cell(item[0] or f"Column {index + 1}")
                                for index, item in enumerate(cursor.description)
                            ]
                        )
                        count = 0
                        while True:
                            batch = cursor.fetchmany(1000)
                            if not batch:
                                break
                            for row in batch:
                                writer.writerow(
                                    [csv_cell(value) for value in row]
                                )
                            count += len(batch)
                            progress(count)
                    return count
            finally:
                connection.rollback()
    except ValueError:
        raise
    except Exception as original:
        e = RuntimeError(
            "CSV could not be written. Check available storage and retry."
            if isinstance(original, OSError)
            else safe_database_error(original, stage)
        )
        logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
        raise e from None
    finally:
        password = ""


class QueryState(rx.State):
    status: str = "idle"
    error: str = ""
    columns: list[str] = []
    rows: list[list[str]] = []
    duration: float = 0.0
    capped: bool = False
    password_revision: int = 0
    example_sql: str = EXAMPLE_SQL
    editor_sql: str = EXAMPLE_SQL
    editor_revision: int = 0
    export_loading: bool = False
    export_rows: int = 0
    export_error: str = ""
    export_message: str = ""

    @rxe.event(background=True)
    async def export_csv(self, form_data: dict[str, Any]):
        password = str(form_data.pop("password", ""))
        async with self:
            if self.status == "loading" or self.export_loading:
                password = ""
                form_data.clear()
                return
            self.export_loading = True
            self.export_rows = 0
            self.export_error = ""
            self.export_message = "Validating and connecting…"
            self.password_revision += 1
            connections = await self.get_state(ConnectionState)
            profile_id = connections.selected_id
        filename = f"query_{secrets.token_hex(32)}.csv"
        path = rx.get_upload_dir() / filename
        complete = False
        try:
            owner = await current_subject()
            sql = validate_select(str(form_data.get("sql", "")))
            if not password:
                raise ValueError("Enter your SQL password for every export.")
            if profile_id:
                async with rx.asession() as session:
                    result = await session.execute(
                        text(
                            "SELECT host, port, database, username FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id"
                        ),
                        {"owner": owner, "id": profile_id},
                    )
                    row = result.mappings().first()
                if row is None:
                    raise ValueError(
                        "The selected profile is unavailable. Use another profile or ad-hoc mode."
                    )
                details = validate_connection(dict(row))
            else:
                details = validate_connection(form_data)
            form_data.clear()
            await asyncio.to_thread(
                path.parent.mkdir, parents=True, exist_ok=True
            )
            updates: queue.SimpleQueue[int] = queue.SimpleQueue()
            task = asyncio.create_task(
                asyncio.to_thread(
                    export_select,
                    str(details["host"]),
                    int(details["port"]),
                    str(details["database"]),
                    str(details["username"]),
                    password,
                    sql,
                    path,
                    updates.put,
                )
            )
            password = ""
            while not task.done():
                await asyncio.wait({task}, timeout=0.3)
                latest = -1
                while not updates.empty():
                    latest = updates.get_nowait()
                async with self:
                    if latest >= 0:
                        self.export_rows = latest
                    self.export_message = "Streaming all result rows to CSV…"
            count = await task
            complete = True
            async with self:
                self.export_rows = count
                self.export_message = (
                    f"Complete: {count:,} rows exported. Download starting."
                )
            yield rx.download(
                url=f"/_upload/{filename}", filename="query-results.csv"
            )
        except (ValueError, RuntimeError) as e:
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            async with self:
                self.export_error = str(e)
                self.export_message = (
                    "Export failed; no partial CSV was offered."
                )
        except Exception:
            e = RuntimeError(
                "Export failed. No partial CSV was offered; please retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            async with self:
                self.export_error = str(e)
                self.export_message = ""
        finally:
            password = ""
            form_data.clear()
            async with self:
                self.export_loading = False
            if complete:
                await asyncio.sleep(120)
            try:
                await asyncio.to_thread(path.unlink, missing_ok=True)
            except OSError:
                e = RuntimeError("Could not remove an expired CSV export.")
                logging.exception(f"Error: {e}", exc_info=(type(e), e, None))

    @rxe.event(background=True)
    async def execute(self, form_data: dict[str, Any]):
        password = str(form_data.pop("password", ""))
        async with self:
            if self.status == "loading" or self.export_loading:
                password = ""
                form_data.clear()
                return
            self.status = "loading"
            self.error = ""
            self.columns = []
            self.rows = []
            self.duration = 0.0
            self.capped = False
            self.password_revision += 1
            connections = await self.get_state(ConnectionState)
            profile_id = connections.selected_id
        started = time.perf_counter()
        try:
            owner = await current_subject()
            sql = validate_select(str(form_data.get("sql", "")))
            if not password:
                raise ValueError("Enter your SQL password for every execution.")
            if profile_id:
                async with rx.asession() as session:
                    result = await session.execute(
                        text(
                            "SELECT host, port, database, username FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id"
                        ),
                        {"owner": owner, "id": profile_id},
                    )
                    row = result.mappings().first()
                if row is None:
                    raise ValueError(
                        "The selected profile is unavailable. Select another profile or use ad-hoc mode."
                    )
                details = validate_connection(dict(row))
            else:
                details = validate_connection(form_data)
            host = str(details["host"])
            database = str(details["database"])
            username = str(details["username"])
            port = int(details["port"])
            form_data.clear()
            columns, rows, capped = await asyncio.to_thread(
                run_select,
                host,
                port,
                database,
                username,
                password,
                sql,
            )
            async with self:
                self.columns = columns
                self.rows = rows
                self.capped = capped
                self.status = "success"
        except (ValueError, RuntimeError) as e:
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            async with self:
                self.error = str(e)
                self.status = "error"
        except Exception:
            e = RuntimeError(
                "Execution could not be completed. Retry with a valid connection and a single SELECT query."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            async with self:
                self.error = str(e)
                self.status = "error"
        finally:
            password = ""
            form_data.clear()
            async with self:
                self.duration = time.perf_counter() - started
