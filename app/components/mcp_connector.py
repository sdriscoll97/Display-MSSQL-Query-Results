import reflex as rx

from app.states.mcp_token_state import MCPTokenState, TokenItem


DESKTOP_CONFIG = """{
  "mcpServers": {
    "sql-workbench": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/claude_desktop_mcp.py"]
    }
  }
}"""


def token_card(token: TokenItem) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                token["name"],
                class_name="break-words text-sm font-semibold text-[#172b42]",
            ),
            rx.el.span(
                token["status"],
                class_name=rx.cond(
                    token["status"] == "Active",
                    "w-fit rounded bg-teal-50 px-2 py-1 text-[10px] font-semibold text-teal-700",
                    "w-fit rounded bg-stone-100 px-2 py-1 text-[10px] font-semibold text-stone-500",
                ),
            ),
            class_name="flex flex-wrap items-center justify-between gap-2",
        ),
        rx.el.p(
            f"Created {token['created']}",
            class_name="mt-2 font-mono text-[11px] text-[#73808a]",
        ),
        rx.el.p(
            f"Expires {token['expires']} · Last used {token['last_used']}",
            class_name="mt-1 font-mono text-[11px] leading-5 text-[#73808a]",
        ),
        rx.el.button(
            rx.icon("key-round", class_name="h-3.5 w-3.5"),
            "Revoke token",
            on_click=lambda: MCPTokenState.revoke_token(token["id"]),
            type="button",
            disabled=token["status"] != "Active",
            class_name="mt-3 flex w-fit items-center gap-2 rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-400",
        ),
        key=token["id"],
        class_name="rounded-lg border border-[#e1e5df] bg-[#fcfdfb] p-4",
    )


def token_manager() -> rx.Component:
    return rx.el.div(
        rx.el.h3(
            "Your access tokens",
            class_name="text-sm font-semibold text-[#172b42]",
        ),
        rx.el.p(
            "Each token grants read-only API access to your own saved items. Give each local client its own token and revoke it when no longer needed.",
            class_name="mt-2 text-xs leading-5 text-[#73808a]",
        ),
        rx.el.form(
            rx.el.div(
                rx.el.label(
                    "Token name",
                    html_for="token-name",
                    class_name="mb-2 block text-xs font-semibold text-[#26364b]",
                ),
                rx.el.input(
                    id="token-name",
                    name="token_name",
                    placeholder="My desktop",
                    required=True,
                    max_length=200,
                    auto_complete="off",
                    class_name="h-10 w-full rounded-lg border border-[#dce0df] bg-white px-3 text-sm text-[#172b42] outline-hidden focus:border-teal-600 focus:ring-2 focus:ring-teal-600/10",
                ),
                class_name="min-w-0 flex-1",
            ),
            rx.el.div(
                rx.el.label(
                    "Expires in",
                    html_for="token-expiry",
                    class_name="mb-2 block text-xs font-semibold text-[#26364b]",
                ),
                rx.el.div(
                    rx.el.select(
                        rx.el.option("7 days", value="7"),
                        rx.el.option("30 days", value="30"),
                        rx.el.option("90 days", value="90"),
                        id="token-expiry",
                        name="expiry_days",
                        default_value="30",
                        class_name="h-10 w-full appearance-none rounded-lg border border-[#dce0df] bg-white py-2 pl-3 pr-9 text-xs text-[#172b42] outline-hidden focus:border-teal-600",
                    ),
                    rx.icon(
                        "chevron-down",
                        class_name="pointer-events-none absolute right-3 top-3 h-4 w-4 text-[#73808a]",
                    ),
                    class_name="relative",
                ),
                class_name="w-28",
            ),
            rx.el.button(
                rx.icon("plus", class_name="h-4 w-4"),
                "Create token",
                type="submit",
                class_name="flex h-10 items-center justify-center gap-2 rounded-lg bg-[#16766b] px-4 text-xs font-semibold text-white hover:bg-[#105e55]",
            ),
            on_submit=MCPTokenState.create_token,
            reset_on_submit=True,
            class_name="mt-5 flex flex-wrap items-end gap-3",
        ),
        rx.cond(
            MCPTokenState.issued_token != "",
            rx.el.div(
                rx.el.p(
                    "Copy once — this token will not be shown again",
                    class_name="text-xs font-semibold text-teal-800",
                ),
                rx.el.code(
                    MCPTokenState.issued_token,
                    class_name="mt-3 block break-all rounded border border-teal-900/10 bg-white p-3 font-mono text-xs text-[#172b42]",
                ),
                rx.el.div(
                    rx.el.button(
                        rx.icon("copy", class_name="h-3.5 w-3.5"),
                        "Copy & hide",
                        type="button",
                        on_click=MCPTokenState.copy_token,
                        class_name="flex items-center gap-2 rounded-lg bg-[#16766b] px-3 py-2 text-xs text-white hover:bg-[#105e55]",
                    ),
                    rx.el.button(
                        "Hide",
                        type="button",
                        on_click=MCPTokenState.dismiss_token,
                        class_name="rounded-lg border border-teal-900/10 bg-white px-3 py-2 text-xs text-teal-800 hover:bg-teal-50",
                    ),
                    class_name="mt-3 flex gap-2",
                ),
                rx.el.p(
                    "If clipboard access is blocked, create a replacement. Do not paste this token into a chat, shared document, or repository.",
                    class_name="mt-3 text-xs leading-5 text-[#54716b]",
                ),
                class_name="mt-4 rounded-lg border border-teal-900/10 bg-[#f0f7f4] p-4",
            ),
        ),
        rx.cond(
            MCPTokenState.error != "",
            rx.el.p(
                MCPTokenState.error,
                role="alert",
                class_name="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-600",
            ),
        ),
        rx.cond(
            MCPTokenState.message != "",
            rx.el.p(
                MCPTokenState.message,
                role="status",
                class_name="mt-3 text-xs leading-5 text-teal-700",
            ),
        ),
        rx.el.div(
            rx.foreach(MCPTokenState.tokens, token_card),
            class_name="mt-5 flex flex-col gap-3",
        ),
        rx.cond(
            MCPTokenState.tokens.length() == 0,
            rx.el.p(
                "No tokens on this page. Creating a token is optional.",
                class_name="mt-4 text-xs text-[#73808a]",
            ),
        ),
        rx.el.div(
            rx.el.button(
                "Previous",
                on_click=MCPTokenState.previous_page,
                disabled=MCPTokenState.page_offset == 0,
                type="button",
                class_name="rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-stone-50 disabled:text-stone-400",
            ),
            rx.el.button(
                rx.icon("refresh-cw", class_name="h-3.5 w-3.5"),
                "Refresh",
                on_click=MCPTokenState.load_tokens,
                type="button",
                class_name="flex items-center gap-2 rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-stone-50",
            ),
            rx.el.button(
                "Next",
                on_click=MCPTokenState.next_page,
                disabled=~MCPTokenState.has_more,
                type="button",
                class_name="rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-stone-50 disabled:text-stone-400",
            ),
            class_name="mt-4 flex flex-wrap gap-2",
        ),
        class_name="min-w-0",
    )


def setup_guidance() -> rx.Component:
    return rx.el.div(
        rx.el.h3(
            "Connect Claude Desktop locally",
            class_name="text-sm font-semibold text-[#172b42]",
        ),
        rx.el.p(
            "Optional Python stdio connector — no hosted MCP service and no Claude account credentials are requested. Your normal browser sign-in remains unchanged.",
            class_name="mt-2 text-xs leading-5 text-[#73808a]",
        ),
        rx.el.ol(
            rx.el.li(
                rx.el.p(
                    "Download the script onto your own machine.",
                    class_name="font-semibold text-[#26364b]",
                ),
                rx.el.button(
                    rx.icon("download", class_name="h-3.5 w-3.5"),
                    "Download Python connector",
                    type="button",
                    on_click=MCPTokenState.download_connector,
                    class_name="mt-2 flex w-fit items-center gap-2 rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-stone-50",
                ),
                rx.el.p(
                    "Create a local virtual environment and install dependencies using its Python:",
                    class_name="mt-2 text-[#73808a]",
                ),
                rx.el.pre(
                    "python -m venv .venv\n.venv/bin/python -m pip install mcp httpx reflex==0.9.12",
                    class_name="mt-2 overflow-x-auto rounded-lg border border-[#e1e5df] bg-[#f7f8f5] p-3 font-mono text-[11px] text-[#26364b]",
                ),
                rx.el.p(
                    "Windows: use .venv\\Scripts\\python.exe for both installation and the command below.",
                    class_name="mt-2 text-[#73808a]",
                ),
            ),
            rx.el.li(
                rx.el.p(
                    "Set private environment variables for the local Python process.",
                    class_name="font-semibold text-[#26364b]",
                ),
                rx.el.p(
                    "WORKBENCH_API_URL: your deployed workbench backend base URL, not the frontend page URL and not a remote MCP URL. Do not include /api/mcp. Use your deployment's backend address; HTTPS is required except http://localhost:8000 for local development.",
                    class_name="mt-2 text-[#73808a]",
                ),
                rx.el.p(
                    "WORKBENCH_API_TOKEN: the token you copied once above. WORKBENCH_SQL_PASSWORDS_JSON: a private JSON object mapping saved profile IDs (as strings) to their SQL passwords. Obtain IDs with list_connections; passwords never appear as tool arguments.",
                    class_name="mt-2 text-[#73808a]",
                ),
                rx.el.p(
                    "Set these using your local OS secret/environment tooling or a private launcher script. Ensure the Desktop-launched Python inherits them: GUI apps often do not inherit terminal variables. Keep the launcher private and outside source control. Do not put secrets into this sample config or send them to Claude.",
                    class_name="mt-2 text-[#73808a]",
                ),
            ),
            rx.el.li(
                rx.el.p(
                    "Add a local stdio server to Claude Desktop.",
                    class_name="font-semibold text-[#26364b]",
                ),
                rx.el.p(
                    "Open Settings → Developer → Edit Config, merge this entry into mcpServers, replace only the absolute local paths, then fully restart Desktop. Use the Python from the virtual environment above (or your private environment-setting launcher as command).",
                    class_name="mt-2 text-[#73808a]",
                ),
                rx.el.pre(
                    DESKTOP_CONFIG,
                    class_name="mt-3 overflow-x-auto rounded-lg border border-[#e1e5df] bg-[#f7f8f5] p-4 font-mono text-[11px] leading-6 text-[#26364b]",
                ),
            ),
            rx.el.li(
                rx.el.p(
                    "Verify tools, then query only saved connections.",
                    class_name="font-semibold text-[#26364b]",
                ),
                rx.el.p(
                    "Start with list_connections and list_saved_queries. run_read_only_query and export_csv accept profile_id and either query_id or sql. Export also needs an absolute local .csv path in an existing directory and will not overwrite files. Review tool calls before approving them.",
                    class_name="mt-2 text-[#73808a]",
                ),
            ),
            class_name="mt-4 list-decimal space-y-5 pl-5 text-xs leading-5 text-[#73808a]",
        ),
        rx.el.div(
            rx.icon(
                "shield-check",
                class_name="mt-0.5 h-4 w-4 shrink-0 text-teal-700",
            ),
            rx.el.p(
                "Use a SELECT-only SQL account. JSON previews are limited to 200 rows, 100 columns, and 2,000 characters per cell. CSV streams all rows with no preview cap and escapes spreadsheet formulas. Timeouts or interrupted streams fail the export; the local connector discards partial downloads. Revocation/expiry blocks new requests, not an already-running query. Results shared with Claude may contain sensitive data — approve access thoughtfully.",
                class_name="text-xs leading-5 text-[#54716b]",
            ),
            class_name="mt-5 flex gap-3 rounded-lg border border-teal-900/10 bg-[#f0f7f4] p-4",
        ),
        class_name="min-w-0",
    )


def mcp_connector() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.icon("plug", class_name="h-4 w-4 text-teal-700"),
                rx.el.h2(
                    "Local MCP connector",
                    class_name="text-base font-semibold text-[#172b42]",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.span(
                "OPTIONAL · STDIO",
                class_name="w-fit rounded border border-[#e1e5e3] bg-[#fafbf9] px-2 py-1 font-mono text-[10px] text-[#718079]",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3 border-b border-[#e8e9e5] px-6 py-5",
        ),
        rx.el.div(
            token_manager(),
            setup_guidance(),
            class_name="grid w-full grid-cols-1 gap-8 p-6 xl:grid-cols-2",
        ),
        class_name="mt-6 w-full rounded-xl border border-[#dfe3df] bg-white",
    )
