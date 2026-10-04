import reflex as rx

import logging
import re
from typing import Any, TypedDict

import reflex_enterprise as rxe
from reflex_enterprise.auth import User
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


class ProfileItem(TypedDict):
    id: int
    name: str


def validate_connection(
    data: dict[str, Any], named: bool = False
) -> dict[str, str | int]:
    values: dict[str, str | int] = {}
    limits = {"host": 512, "database": 128, "username": 128}
    if named:
        limits["name"] = 200
    for field, maximum in limits.items():
        value = str(data.get(field, "")).strip()
        if (
            not value
            or len(value) > maximum
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError(
                f"{field.capitalize()} is required and must be at most {maximum} characters, without control characters."
            )
        values[field] = value
    host = str(values["host"])
    if not re.fullmatch(r"[A-Za-z0-9_.:\-]+", host):
        raise ValueError(
            "Server must be a hostname or IP address, without spaces, URLs, or an embedded port. Use the TCP port field."
        )
    port = str(data.get("port", "1433")).strip()
    if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("Port must be a number between 1 and 65535.")
    values["port"] = int(port)
    return values


async def current_subject() -> str:
    user = await User.current() or {}
    subject = user.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError(
            "Please sign in again before accessing connection profiles."
        )
    return subject


class ConnectionState(rx.State):
    profiles: list[ProfileItem] = []
    selected_id: int = 0
    name: str = ""
    host: str = ""
    port: str = "1433"
    database: str = ""
    username: str = ""
    revision: int = 0
    message: str = ""
    error: str = ""
    delete_pending: bool = False
    page_offset: int = 0
    has_more: bool = False

    @rxe.event
    async def load_profiles(self):
        self.error = ""
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "SELECT id, name FROM sql_server_connection_profiles WHERE owner_subject = :owner ORDER BY name, id LIMIT 51 OFFSET :offset"
                    ),
                    {"owner": owner, "offset": self.page_offset},
                )
                rows = result.mappings().all()
            self.profiles = [
                {"id": int(row["id"]), "name": str(row["name"])}
                for row in rows[:50]
            ]
            self.has_more = len(rows) > 50
        except Exception as original:
            e = RuntimeError(
                "Could not load your connection profiles. Please retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.profiles = []
            self.has_more = False
            self.error = str(e)

    @rxe.event
    async def load_page(self):
        self.new_connection()
        self.page_offset = 0
        yield ConnectionState.load_profiles

    @rxe.event
    def previous_page(self):
        self.page_offset = max(0, self.page_offset - 50)
        return ConnectionState.load_profiles

    @rxe.event
    def next_page(self):
        if self.has_more:
            self.page_offset += 50
        return ConnectionState.load_profiles

    @rxe.event
    def new_connection(self):
        self.selected_id = 0
        self.name = ""
        self.host = ""
        self.port = "1433"
        self.database = ""
        self.username = ""
        self.revision += 1
        self.message = "Ad-hoc mode: enter details to run without saving."
        self.error = ""
        self.delete_pending = False

    @rxe.event
    async def select_profile(self, profile_id: int):
        self.error = ""
        self.message = ""
        self.delete_pending = False
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "SELECT id, name, host, port, database, username FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id"
                    ),
                    {"owner": owner, "id": profile_id},
                )
                row = result.mappings().first()
            if row is None:
                raise ValueError(
                    "This profile is unavailable. Refresh the list and try again."
                )
            self.selected_id = int(row["id"])
            self.name = str(row["name"])
            self.host = str(row["host"])
            self.port = str(row["port"])
            self.database = str(row["database"])
            self.username = str(row["username"])
            self.revision += 1
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.new_connection()
            self.error = str(e)
        except Exception:
            e = RuntimeError("Could not open the profile. Please retry.")
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.new_connection()
            self.error = str(e)

    @rxe.event
    async def save_profile(self, form_data: dict[str, Any]):
        self.error = ""
        self.message = ""
        try:
            owner = await current_subject()
            data = validate_connection(
                {
                    "name": form_data.get("profile_name", ""),
                    "host": form_data.get("host", ""),
                    "port": form_data.get("port", ""),
                    "database": form_data.get("database", ""),
                    "username": form_data.get("username", ""),
                },
                named=True,
            )
            params = {**data, "owner": owner, "id": self.selected_id}
            async with rx.asession() as session:
                if self.selected_id:
                    result = await session.execute(
                        text(
                            "UPDATE sql_server_connection_profiles SET name = :name, host = :host, port = :port, database = :database, username = :username, updated_at = CURRENT_TIMESTAMP WHERE owner_subject = :owner AND id = :id RETURNING id"
                        ),
                        params,
                    )
                else:
                    result = await session.execute(
                        text(
                            "INSERT INTO sql_server_connection_profiles (owner_subject, name, host, port, database, username) VALUES (:owner, :name, :host, :port, :database, :username) RETURNING id"
                        ),
                        params,
                    )
                saved_id = result.scalar_one_or_none()
                if saved_id is None:
                    raise ValueError(
                        "This profile no longer exists. Choose ad-hoc mode to save a new one."
                    )
                await session.commit()
            self.selected_id = int(saved_id)
            self.name = str(data["name"])
            self.host = str(data["host"])
            self.port = str(data["port"])
            self.database = str(data["database"])
            self.username = str(data["username"])
            self.revision += 1
            self.delete_pending = False
            self.message = "Profile saved. Passwords are never saved."
            yield ConnectionState.load_profiles
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except IntegrityError:
            e = RuntimeError(
                "A profile with this name already exists in your account. Choose a different name."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        except Exception:
            e = RuntimeError(
                "Could not save your profile. Your changes were not saved; please retry."
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
    async def delete_profile(self):
        self.error = ""
        self.message = ""
        if not self.delete_pending or not self.selected_id:
            return
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "DELETE FROM sql_server_connection_profiles WHERE owner_subject = :owner AND id = :id RETURNING id"
                    ),
                    {"owner": owner, "id": self.selected_id},
                )
                if result.scalar_one_or_none() is None:
                    raise ValueError(
                        "This profile no longer exists. Refresh your list."
                    )
                await session.commit()
            self.new_connection()
            self.message = "Profile deleted."
            self.page_offset = 0
            yield ConnectionState.load_profiles
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except IntegrityError:
            e = RuntimeError(
                "Cannot delete this profile because a saved item still references it."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        except Exception:
            e = RuntimeError(
                "Could not delete the profile. It has not been deleted; please retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        finally:
            self.delete_pending = False
