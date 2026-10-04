import reflex as rx
import reflex_enterprise as rxe

from app.components.workbench import workbench
from app.components.evil_eye import evil_eye_background
from app.states.saved_query_state import SavedQueryState
from app.states.connection_state import ConnectionState
from app.states.mcp_token_state import MCPTokenState
from app.mcp_api import mcp_api


def index() -> rx.Component:
    return rx.el.div(
        evil_eye_background(),
        workbench(),
        class_name="relative isolate min-h-dvh w-full bg-[#f4f5f0] text-[#172b42]",
    )


app = rxe.App(
    api_transformer=mcp_api,
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(
            rel="preconnect",
            href="https://fonts.gstatic.com",
            cross_origin="",
        ),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(
    index,
    route="/",
    on_load=[
        ConnectionState.load_page,
        SavedQueryState.load_page,
        MCPTokenState.load_page,
    ],
    title="SQL Workbench | Read-only query explorer",
    description="Explore read-only SQL Server results with private saved connection profiles and execution-only passwords.",
)
