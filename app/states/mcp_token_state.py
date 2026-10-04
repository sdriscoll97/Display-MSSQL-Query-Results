import reflex as rx

import hashlib
import logging
import secrets
from pathlib import Path
from typing import Any, TypedDict

import reflex_enterprise as rxe
from sqlalchemy import text

from app.states.connection_state import current_subject


class TokenItem(TypedDict):
    id: int
    name: str
    created: str
    expires: str
    last_used: str
    status: str


class MCPTokenState(rx.State):
    tokens: list[TokenItem] = []
    issued_token: str = ""
    error: str = ""
    message: str = ""
    page_offset: int = 0
    has_more: bool = False

    @rxe.event
    async def load_page(self):
        self.issued_token = ""
        self.tokens = []
        self.error = ""
        self.message = ""
        self.page_offset = 0
        yield MCPTokenState.load_tokens

    @rxe.event
    async def load_tokens(self):
        self.error = ""
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "SELECT id, name, created_at, expires_at, last_used_at, CASE WHEN revoked_at IS NOT NULL THEN 'Revoked' WHEN expires_at <= CURRENT_TIMESTAMP THEN 'Expired' ELSE 'Active' END AS status FROM mcp_access_tokens WHERE owner_subject = :owner ORDER BY created_at DESC, id DESC LIMIT 21 OFFSET :offset"
                    ),
                    {"owner": owner, "offset": self.page_offset},
                )
                rows = result.mappings().all()
            self.tokens = [
                {
                    "id": int(row["id"]),
                    "name": str(row["name"]),
                    "created": row["created_at"].strftime("%Y-%m-%d %H:%M UTC"),
                    "expires": row["expires_at"].strftime("%Y-%m-%d %H:%M UTC")
                    if row["expires_at"]
                    else "No expiry",
                    "last_used": row["last_used_at"].strftime(
                        "%Y-%m-%d %H:%M UTC"
                    )
                    if row["last_used_at"]
                    else "Never",
                    "status": str(row["status"]),
                }
                for row in rows[:20]
            ]
            self.has_more = len(rows) > 20
        except Exception:
            e = RuntimeError("Could not load access tokens. Please retry.")
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.tokens = []
            self.has_more = False
            self.error = str(e)

    @rxe.event
    async def create_token(self, form_data: dict[str, Any]):
        self.error = ""
        self.message = ""
        self.issued_token = ""
        plaintext = ""
        try:
            owner = await current_subject()
            name = str(form_data.get("token_name", "")).strip()
            days = str(form_data.get("expiry_days", "30"))
            if (
                not name
                or len(name) > 200
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
            ):
                raise ValueError(
                    "Use a token name of 1–200 characters without control characters."
                )
            if days not in {"7", "30", "90"}:
                raise ValueError("Choose an expiry of 7, 30, or 90 days.")
            plaintext = secrets.token_urlsafe(48)
            digest = hashlib.sha256(plaintext.encode("ascii")).hexdigest()
            async with rx.asession() as session:
                await session.execute(
                    text(
                        "INSERT INTO mcp_access_tokens (owner_subject, name, token_hash, hash_algorithm, expires_at) VALUES (:owner, :name, :digest, 'sha256', CURRENT_TIMESTAMP + make_interval(days => :days))"
                    ),
                    {
                        "owner": owner,
                        "name": name,
                        "digest": digest,
                        "days": int(days),
                    },
                )
                await session.commit()
            self.issued_token = plaintext
            self.page_offset = 0
            self.message = (
                "Token created. Copy it now; it cannot be retrieved later."
            )
            yield MCPTokenState.load_tokens
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except Exception:
            e = RuntimeError("Could not create the token. Please retry.")
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)
        finally:
            plaintext = ""
            form_data.clear()

    @rxe.event
    def copy_token(self):
        token = self.issued_token
        self.issued_token = ""
        self.message = (
            "Token copied and hidden. Store it securely on your own machine."
        )
        if token:
            return rx.set_clipboard(token)

    @rxe.event
    def dismiss_token(self):
        self.issued_token = ""
        self.message = "Token hidden. If you did not save it, revoke it and create a replacement."

    @rxe.event
    async def revoke_token(self, token_id: int):
        self.issued_token = ""
        self.error = ""
        try:
            owner = await current_subject()
            async with rx.asession() as session:
                result = await session.execute(
                    text(
                        "UPDATE mcp_access_tokens SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE owner_subject = :owner AND id = :id RETURNING id"
                    ),
                    {"owner": owner, "id": token_id},
                )
                if result.scalar_one_or_none() is None:
                    raise ValueError("Token unavailable. Refresh your list.")
                await session.commit()
            self.message = (
                "Token revoked. New API requests with this token are denied."
            )
            yield MCPTokenState.load_tokens
        except ValueError as e:
            logging.exception(f"Error: {e}")
            self.error = str(e)
        except Exception:
            e = RuntimeError("Could not revoke the token. Please retry.")
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)

    @rxe.event
    def download_connector(self):
        try:
            source = (
                Path(__file__)
                .resolve()
                .parents[1]
                .joinpath("claude_desktop_mcp.py")
                .read_text(encoding="utf-8")
            )
            return rx.download(data=source, filename="claude_desktop_mcp.py")
        except OSError:
            e = RuntimeError(
                "Could not download the local connector. Please retry."
            )
            logging.exception(f"Error: {e}", exc_info=(type(e), e, None))
            self.error = str(e)

    @rxe.event
    def previous_page(self):
        self.page_offset = max(0, self.page_offset - 20)
        return MCPTokenState.load_tokens

    @rxe.event
    def next_page(self):
        if self.has_more:
            self.page_offset += 20
        return MCPTokenState.load_tokens
