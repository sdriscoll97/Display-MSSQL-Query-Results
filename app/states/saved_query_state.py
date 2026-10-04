import reflex as rx

import logging
from typing import Any, TypedDict

import reflex_enterprise as rxe
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.states.connection_state import ConnectionState, current_subject
from app.states.query_state import QueryState, validate_select


class SavedQueryItem(TypedDict):
    id: int
    name: str


class SavedQueryState(rx.State):
    queries: list[SavedQueryItem] = []
    selected_id: int = 0
    name: str = ""
    associated: bool = False
    error: str = ""
    message: str = ""
    delete_pending: bool = False
    page_offset: int = 0
    has_more: bool = False

    @rxe.event
    async def load_queries(self):
        self.error = ""
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "SELECT id, name FROM saved_sql_queries WHERE owner_subject = :owner ORDER BY name, id LIMIT 51 OFFSET :offset"
                    ),
                    {"owner": owner, "offset": self.page_offset},
                )
                rows = result.mappings().all()
            self.queries = [
                {"id": int(row["id"]), "name": str(row["name"])}
                for row in rows[:50]
            ]
            self.has_more = len(rows) > 50
        except Exception:
            e = RuntimeError("Could not load your saved queries. Please retry.")
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.queries = []
            self.has_more = False
            self.error = str(e)

    @rxe.event
    async def load_page(self):
        self.selected_id = 0
        self.name = ""
        self.associated = False
        self.delete_pending = False
        self.message = ""
        self.page_offset = 0
        query = await self.get_state(QueryState)
        query.editor_sql = query.example_sql
        query.editor_revision += 1
        yield SavedQueryState.load_queries

    @rxe.event
    def previous_page(self):
        self.page_offset = max(0, self.page_offset - 50)
        return SavedQueryState.load_queries

    @rxe.event
    def next_page(self):
        if self.has_more:
            self.page_offset += 50
        return SavedQueryState.load_queries

    @rxe.event
    def ad_hoc(self):
        self.selected_id = 0
        self.name = ""
        self.associated = False
        self.delete_pending = False
        self.error = ""
        self.message = "Ad-hoc query: the editor is kept. Save with a new name to create a query."

    @rxe.event
    async def select_query(self, query_id: int):
        self.error = ""
        self.message = ""
        self.delete_pending = False
        try:
            owner = await current_subject()
            query = await self.get_state(QueryState)
            if query.status == "loading" or query.export_loading:
                return
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "SELECT id, name, sql_text, connection_profile_id FROM saved_sql_queries WHERE owner_subject = :owner AND id = :id"
                    ),
                    {"owner": owner, "id": query_id},
                )
                row = result.mappings().first()
                if row is None:
                    raise ValueError(
                        "This saved query is unavailable. Refresh the list."
                    )
                validate_select(str(row["sql_text"]))
                profile_id = int(row["connection_profile_id"] or 0)
                profile = None
                if profile_id:
                    profile_result = await session.execute(
                        text(
                            "SELECT id, name, host, port, database, username FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id"
                        ),
                        {"owner": owner, "id": profile_id},
                    )
                    profile = profile_result.mappings().first()
                    if profile is None:
                        raise ValueError(
                            "The associated profile is unavailable. This query was not opened."
                        )
            connections = await self.get_state(ConnectionState)
            if profile is not None:
                connections.selected_id = profile_id
                connections.name = str(profile["name"])
                connections.host = str(profile["host"])
                connections.port = str(profile["port"])
                connections.database = str(profile["database"])
                connections.username = str(profile["username"])
                connections.revision += 1
                connections.delete_pending = False
                connections.error = ""
                connections.message = "Opened the saved query's associated profile. Re-enter its password."
            self.selected_id = int(row["id"])
            self.name = str(row["name"])
            self.associated = bool(profile_id)
            query.editor_sql = str(row["sql_text"])
            query.editor_revision += 1
            query.password_revision += 1
            self.message = "Query opened. Unassociated queries keep your current connection."
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except Exception:
            e = RuntimeError("Could not open your saved query. Please retry.")
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)

    @rxe.event
    async def save_query(self, form_data: dict[str, Any]):
        self.error = ""
        self.message = ""
        try:
            owner = await current_subject()
            name = str(form_data.get("query_name", "")).strip()
            if (
                not name
                or len(name) > 200
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
            ):
                raise ValueError(
                    "Query name is required: at most 200 characters, without control characters."
                )
            sql = str(form_data.get("sql", ""))
            validate_select(sql)
            connections = await self.get_state(ConnectionState)
            profile_id = (
                connections.selected_id
                if form_data.get("associate") is True
                else 0
            )
            if form_data.get("associate") is True and not profile_id:
                raise ValueError(
                    "Select a saved connection profile before associating this query."
                )
            params = {
                "owner": owner,
                "id": self.selected_id,
                "name": name,
                "sql": sql,
                "profile": profile_id or None,
            }
            async with rx.asession() as session:
                if profile_id:
                    profile = await session.execute(
                        text(
                            "SELECT id FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id FOR KEY SHARE"
                        ),
                        {"owner": owner, "id": profile_id},
                    )
                    if profile.scalar_one_or_none() is None:
                        raise ValueError(
                            "The selected profile is unavailable or does not belong to your account."
                        )
                if self.selected_id:
                    result = await session.execute(
                        text(
                            "UPDATE saved_sql_queries SET name = :name, sql_text = :sql, connection_profile_id = :profile, updated_at = CURRENT_TIMESTAMP WHERE owner_subject = :owner AND id = :id RETURNING id"
                        ),
                        params,
                    )
                else:
                    result = await session.execute(
                        text(
                            "INSERT INTO saved_sql_queries (owner_subject, name, sql_text, connection_profile_id) VALUES (:owner, :name, :sql, :profile) RETURNING id"
                        ),
                        params,
                    )
                saved_id = result.scalar_one_or_none()
                if saved_id is None:
                    raise ValueError(
                        "This query no longer exists. Choose ad-hoc mode to save a new query."
                    )
                await session.commit()
            self.selected_id = int(saved_id)
            self.name = name
            self.associated = bool(profile_id)
            self.delete_pending = False
            self.message = (
                "Query saved privately. No password was captured or saved."
            )
            yield SavedQueryState.load_queries
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except IntegrityError as original:
            code = getattr(getattr(original, "orig", None), "sqlstate", "")
            e = RuntimeError(
                "A query with this name already exists in your account. Choose another name."
                if code == "23505"
                else "The associated profile changed or is unavailable. Refresh your profiles and retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        except Exception:
            e = RuntimeError(
                "Could not save the query. Your changes were not saved; please retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        finally:
            form_data.clear()

    @rxe.event
    def ask_delete(self):
        self.delete_pending = self.selected_id > 0

    @rxe.event
    def cancel_delete(self):
        self.delete_pending = False

    @rxe.event
    async def delete_query(self):
        self.error = ""
        self.message = ""
        if not self.delete_pending or not self.selected_id:
            return
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "DELETE FROM saved_sql_queries WHERE owner_subject = :owner AND id = :id RETURNING id"
                    ),
                    {"owner": owner, "id": self.selected_id},
                )
                if result.scalar_one_or_none() is None:
                    raise ValueError(
                        "This query no longer exists. Refresh your list."
                    )
                await session.commit()
            self.ad_hoc()
            self.message = "Saved query deleted. Its SQL remains in the editor for ad-hoc use."
            self.page_offset = 0
            yield SavedQueryState.load_queries
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except Exception:
            e = RuntimeError(
                "Could not delete this query. It has not been deleted; please retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        finally:
            self.delete_pending = False
