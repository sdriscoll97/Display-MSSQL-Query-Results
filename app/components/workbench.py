import reflex as rx

from reflex_enterprise.auth import User

from app.components.connection_manager import connection_manager
from app.components.evil_eye import appearance_toggle
from app.components.saved_queries import csv_export, saved_queries
from app.components.mcp_connector import mcp_connector
from app.states.mcp_token_state import MCPTokenState
from app.states.connection_state import ConnectionState
from app.states.query_state import QueryState


def connection_field(
    label: str,
    name: str,
    placeholder: str,
    input_type: str = "text",
    default: str = "",
) -> rx.Component:
    return rx.el.div(
        rx.el.label(
            label,
            html_for=name,
            class_name="mb-2 block text-xs font-semibold text-[#26364b]",
        ),
        rx.el.input(
            id=name,
            name=name,
            type=input_type,
            placeholder=placeholder,
            default_value=default,
            key=default,
            required=True,
            auto_complete="off",
            disabled=(QueryState.status == "loading")
            | QueryState.export_loading,
            class_name="h-11 w-full rounded-lg border border-[#dce0df] bg-white px-3 font-mono text-sm text-[#172b42] placeholder:text-[#a0a7ac] outline-hidden transition focus:border-teal-600 focus:ring-2 focus:ring-teal-600/10 disabled:bg-stone-50 disabled:text-stone-400",
        ),
        class_name="min-w-0",
    )


def connection_panel() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.span("01", class_name="font-mono text-xs text-teal-700"),
                rx.el.h2(
                    "Connection",
                    class_name="text-base font-semibold text-[#172b42]",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.icon("database", class_name="h-4 w-4 text-[#7c8992]"),
            class_name="flex items-center justify-between border-b border-[#e8e9e5] px-6 py-5",
        ),
        rx.el.div(
            rx.el.p(
                "Connect on your terms.",
                class_name="text-sm font-medium text-[#26364b]",
            ),
            rx.el.p(
                "Save endpoint details privately, or run an ad-hoc connection. Passwords are never saved.",
                class_name="mt-1 text-xs leading-5 text-[#73808a]",
            ),
            connection_manager(),
            rx.el.div(
                connection_field(
                    "Host / server",
                    "host",
                    "sql.example.com",
                    default=ConnectionState.host,
                ),
                class_name="mt-6",
            ),
            rx.el.div(
                connection_field(
                    "TCP port", "port", "1433", "number", ConnectionState.port
                ),
                connection_field(
                    "Database",
                    "database",
                    "Database name",
                    default=ConnectionState.database,
                ),
                class_name="mt-4 grid grid-cols-[100px_1fr] gap-4",
            ),
            rx.el.div(
                connection_field(
                    "Username",
                    "username",
                    "Read-only SQL user",
                    default=ConnectionState.username,
                ),
                class_name="mt-4",
            ),
            rx.el.div(
                rx.el.label(
                    "Password",
                    html_for="password",
                    class_name="mb-2 block text-xs font-semibold text-[#26364b]",
                ),
                rx.el.input(
                    id="password",
                    name="password",
                    type="password",
                    required=True,
                    default_value="",
                    key=f"{QueryState.password_revision}-{ConnectionState.revision}",
                    auto_complete="new-password",
                    placeholder="Enter password",
                    disabled=(QueryState.status == "loading")
                    | QueryState.export_loading,
                    class_name="h-11 w-full rounded-lg border border-[#dce0df] bg-white px-3 font-mono text-sm text-[#172b42] placeholder:text-[#a0a7ac] outline-hidden focus:border-teal-600 focus:ring-2 focus:ring-teal-600/10 disabled:bg-stone-50",
                ),
                rx.el.p(
                    "Cleared when you execute or export. Re-enter for each operation.",
                    class_name="mt-2 text-[11px] text-[#73808a]",
                ),
                class_name="mt-4",
            ),
            rx.el.div(
                appearance_toggle(),
                rx.icon(
                    "shield-check",
                    class_name="mt-0.5 h-4 w-4 shrink-0 text-teal-700",
                ),
                rx.el.div(
                    rx.el.p(
                        "Use a read-only database user",
                        class_name="text-xs font-semibold text-[#234e49]",
                    ),
                    rx.el.p(
                        "Grant SELECT only. Query checks are an extra safeguard, not a replacement for database permissions.",
                        class_name="mt-1 text-xs leading-5 text-[#54716b]",
                    ),
                ),
                class_name="mt-6 flex gap-3 rounded-lg border border-teal-900/10 bg-[#f0f7f4] p-4",
            ),
            class_name="p-6",
        ),
        class_name="min-w-0 rounded-xl border border-[#dfe3df] bg-white",
    )


def editor_panel() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.el.span("02", class_name="font-mono text-xs text-teal-700"),
                rx.el.h2(
                    "Query editor",
                    class_name="text-base font-semibold text-[#172b42]",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.span(
                "T-SQL",
                class_name="w-fit rounded border border-[#e1e5e3] bg-[#fafbf9] px-2 py-1 font-mono text-[10px] font-medium tracking-wide text-[#718079]",
            ),
            class_name="flex items-center justify-between border-b border-[#e8e9e5] px-6 py-5",
        ),
        rx.el.div(
            saved_queries(),
            rx.el.div(
                rx.el.label(
                    "SQL statement",
                    html_for="sql",
                    class_name="text-xs font-semibold text-[#26364b]",
                ),
                rx.el.span(
                    "Single SELECT only", class_name="text-xs text-[#73808a]"
                ),
                class_name="mb-3 flex items-center justify-between",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon("code", class_name="h-3.5 w-3.5 text-teal-700"),
                    rx.el.span(
                        "query.sql",
                        class_name="font-mono text-[11px] text-[#75808b]",
                    ),
                    rx.el.span(
                        "Example · database table metadata",
                        class_name="ml-auto hidden text-[10px] text-[#85918b] sm:block",
                    ),
                    class_name="flex items-center gap-2 border-b border-[#e6e9e4] bg-[#f7f8f5] px-4 py-3",
                ),
                rx.el.textarea(
                    id="sql",
                    name="sql",
                    default_value=QueryState.editor_sql,
                    key=QueryState.editor_revision,
                    required=True,
                    spell_check=False,
                    disabled=QueryState.status == "loading",
                    aria_label="SQL query editor",
                    class_name="block min-h-[272px] w-full resize-y bg-[#fcfdfb] p-5 font-mono text-[13px] leading-7 text-[#1e625c] outline-hidden focus:bg-white focus:ring-2 focus:ring-inset focus:ring-teal-600/20 disabled:text-stone-400",
                ),
                class_name="overflow-hidden rounded-lg border border-[#dce0df]",
            ),
            rx.el.div(
                rx.icon(
                    "info",
                    class_name="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#839089]",
                ),
                rx.el.p(
                    "The example reads table names from your database. Replace it with your own SELECT; no sample results are generated.",
                    class_name="text-xs leading-5 text-[#73808a]",
                ),
                class_name="mt-4 flex gap-2",
            ),
            rx.el.div(
                rx.el.div(
                    rx.icon(
                        "list-filter", class_name="h-3.5 w-3.5 text-[#73808a]"
                    ),
                    rx.el.span(
                        "200-row preview limit",
                        class_name="text-xs text-[#73808a]",
                    ),
                    class_name="flex items-center gap-2",
                ),
                rx.el.button(
                    rx.cond(
                        QueryState.status == "loading",
                        rx.icon(
                            "loader-circle", class_name="h-4 w-4 animate-spin"
                        ),
                        rx.icon("play", class_name="h-4 w-4"),
                    ),
                    rx.cond(
                        QueryState.status == "loading",
                        "Executing…",
                        "Execute query",
                    ),
                    type="submit",
                    disabled=QueryState.status == "loading",
                    class_name="flex items-center justify-center gap-2 rounded-lg bg-[#16766b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#105e55] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-wait disabled:bg-[#6b9992]",
                ),
                class_name="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-[#e8e9e5] pt-5",
            ),
            csv_export(),
            class_name="p-6",
        ),
        class_name="min-w-0 rounded-xl border border-[#dfe3df] bg-white",
    )


def empty_message(icon: str, title: str, description: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(icon, class_name="h-6 w-6 text-[#7e9b93]"),
            class_name="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-[#e2eae4] bg-[#f4f8f4]",
        ),
        rx.el.h3(title, class_name="text-sm font-semibold text-[#26364b]"),
        rx.el.p(
            description,
            class_name="mt-2 max-w-md text-center text-xs leading-5 text-[#73808a]",
        ),
        class_name="flex min-h-[230px] flex-col items-center justify-center px-6 py-10",
    )


def result_table() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.table(
                rx.el.thead(
                    rx.el.tr(
                        rx.el.th(
                            "#",
                            class_name="sticky top-0 border-b border-[#dde5e0] bg-[#f4f7f4] px-5 py-3 text-left font-normal text-[#8b9692]",
                        ),
                        rx.foreach(
                            QueryState.columns,
                            lambda column: rx.el.th(
                                rx.el.div(
                                    rx.icon(
                                        "columns-2",
                                        class_name="h-3 w-3 text-[#8b9692]",
                                    ),
                                    column,
                                    class_name="flex items-center gap-2",
                                ),
                                class_name="sticky top-0 whitespace-nowrap border-b border-[#dde5e0] bg-[#f4f7f4] px-5 py-3 text-left font-medium text-[#30473f]",
                            ),
                        ),
                    )
                ),
                rx.el.tbody(
                    rx.foreach(
                        QueryState.rows,
                        lambda row, index: rx.el.tr(
                            rx.el.td(
                                index + 1,
                                class_name="w-14 border-b border-[#edf0ec] px-5 py-3 text-[#94a09a]",
                            ),
                            rx.foreach(
                                row,
                                lambda cell: rx.el.td(
                                    cell,
                                    title=cell,
                                    class_name=rx.cond(
                                        cell == "NULL",
                                        "max-w-[480px] truncate whitespace-nowrap border-b border-[#edf0ec] px-5 py-3 italic text-[#9aa59f]",
                                        "max-w-[480px] truncate whitespace-nowrap border-b border-[#edf0ec] px-5 py-3 text-[#26364b]",
                                    ),
                                ),
                            ),
                            key=index,
                            class_name="odd:bg-white even:bg-[#fafbf9] hover:bg-teal-50/60",
                        ),
                    )
                ),
                class_name="table-auto w-full font-mono text-xs",
            ),
            class_name="max-h-[480px] w-full overflow-auto",
            tab_index=0,
            aria_label="Scrollable query results",
        ),
        rx.cond(
            QueryState.rows.length() == 0,
            empty_message(
                "search-x",
                "No matching rows",
                "The query completed successfully and returned column headers, but no rows. Try adjusting your filters.",
            ),
        ),
        class_name="w-full overflow-hidden",
    )


def results_panel() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.div(
                rx.icon("table-2", class_name="h-4 w-4 text-teal-700"),
                rx.el.h2(
                    "Results",
                    class_name="text-base font-semibold text-[#172b42]",
                ),
                rx.el.span(
                    "LIVE QUERY OUTPUT",
                    class_name="ml-1 hidden font-mono text-[9px] tracking-[0.15em] text-[#8a9590] sm:block",
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.div(
                rx.match(
                    QueryState.status,
                    (
                        "idle",
                        rx.el.span(
                            "Awaiting execution",
                            class_name="text-xs text-[#829087]",
                        ),
                    ),
                    (
                        "loading",
                        rx.el.span(
                            "Running query…", class_name="text-xs text-teal-700"
                        ),
                    ),
                    (
                        "error",
                        rx.el.span(
                            "Execution failed",
                            class_name="text-xs text-red-600",
                        ),
                    ),
                    rx.el.div(
                        rx.el.span(
                            f"{QueryState.rows.length()} rows",
                            class_name="font-mono text-xs text-[#26364b]",
                        ),
                        rx.el.span("/", class_name="text-[#c2c9c3]"),
                        rx.icon(
                            "timer", class_name="h-3.5 w-3.5 text-[#829087]"
                        ),
                        rx.el.span(
                            f"{QueryState.duration:.2f}s",
                            class_name="font-mono text-xs text-[#73808a]",
                        ),
                        class_name="flex items-center gap-2",
                    ),
                ),
                class_name="flex items-center gap-3",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3 border-b border-[#e8e9e5] px-6 py-5",
        ),
        rx.el.div(
            rx.match(
                QueryState.status,
                (
                    "idle",
                    empty_message(
                        "table-2",
                        "Your results will appear here",
                        "Enter your connection details and execute a SELECT to explore real data. No database is connected yet.",
                    ),
                ),
                (
                    "loading",
                    rx.el.div(
                        rx.icon(
                            "loader-circle",
                            class_name="mb-4 h-7 w-7 animate-spin text-teal-700",
                        ),
                        rx.el.p(
                            "Connecting and executing your query",
                            class_name="text-sm font-medium text-[#26364b]",
                        ),
                        rx.el.p(
                            "8s login timeout · 20s query timeout",
                            class_name="mt-2 font-mono text-xs text-[#73808a]",
                        ),
                        class_name="flex min-h-[230px] flex-col items-center justify-center p-6",
                    ),
                ),
                (
                    "error",
                    rx.el.div(
                        rx.icon(
                            "circle-alert",
                            class_name="mt-1 h-5 w-5 shrink-0 text-red-600",
                        ),
                        rx.el.div(
                            rx.el.h3(
                                "Unable to execute",
                                class_name="text-sm font-semibold text-[#26364b]",
                            ),
                            rx.el.p(
                                QueryState.error,
                                class_name="mt-2 text-sm leading-6 text-[#6f5555]",
                            ),
                            rx.el.p(
                                f"Elapsed: {QueryState.duration:.2f}s · Re-enter your password before retrying.",
                                class_name="mt-4 font-mono text-[11px] text-[#8b7474]",
                            ),
                        ),
                        class_name="m-6 flex gap-4 rounded-lg border border-red-200 bg-red-50/60 p-5",
                        role="alert",
                    ),
                ),
                result_table(),
            ),
            aria_live="polite",
            aria_busy=QueryState.status == "loading",
        ),
        rx.el.div(
            rx.cond(
                QueryState.capped,
                rx.el.div(
                    rx.icon(
                        "triangle-alert",
                        class_name="h-3.5 w-3.5 text-amber-600",
                    ),
                    rx.el.span(
                        "Preview capped: first 200 rows shown. More rows exist; this is not the total row count.",
                        class_name="text-xs text-amber-800",
                    ),
                    class_name="flex items-center gap-2",
                ),
                rx.el.div(
                    rx.icon(
                        "sliders-horizontal",
                        class_name="h-3.5 w-3.5 text-[#88948c]",
                    ),
                    rx.el.span(
                        "Maximum 200 rows · 100 columns · long values truncated at 2,000 characters",
                        class_name="text-[11px] text-[#73808a]",
                    ),
                    class_name="flex items-center gap-2",
                ),
            ),
            rx.el.span(
                "Scroll horizontally for wide results",
                class_name="hidden text-[11px] text-[#8a9590] md:block",
            ),
            class_name="flex flex-wrap items-center justify-between gap-2 border-t border-[#e8e9e5] bg-[#fcfdfb] px-6 py-3",
        ),
        class_name="mt-6 w-full overflow-hidden rounded-xl border border-[#dfe3df] bg-white",
    )


def workbench() -> rx.Component:
    return rx.el.main(
        rx.el.header(
            rx.el.div(
                rx.el.div(
                    rx.icon("database", class_name="h-5 w-5 text-white"),
                    class_name="flex h-10 w-10 items-center justify-center rounded-xl bg-[#16766b]",
                ),
                rx.el.div(
                    rx.el.h1(
                        "SQL Workbench",
                        class_name="text-xl font-semibold tracking-tight text-[#172b42]",
                    ),
                    rx.el.p(
                        "A focused space for read-only exploration",
                        class_name="mt-1 text-xs text-[#73808a]",
                    ),
                ),
                class_name="flex items-center gap-3",
            ),
            rx.el.div(
                rx.icon("user-round", class_name="h-4 w-4 text-teal-700"),
                rx.el.div(
                    rx.el.p(
                        rx.cond(User.name != "", User.name, "Signed in"),
                        class_name="text-xs font-semibold text-[#26364b]",
                    ),
                    rx.el.p(
                        User.email,
                        class_name="max-w-48 truncate text-[11px] text-[#73808a]",
                    ),
                ),
                rx.el.button(
                    rx.icon("log-out", class_name="h-3.5 w-3.5"),
                    "Sign out",
                    type="button",
                    on_click=[MCPTokenState.dismiss_token, User.logout],
                    class_name="ml-2 flex items-center gap-2 rounded-lg border border-[#dce3dc] bg-white px-3 py-2 text-xs text-[#26364b] hover:bg-stone-50",
                ),
                class_name="flex w-fit items-center gap-2",
            ),
            class_name="flex flex-wrap items-center justify-between gap-4 border-b border-[#dde2da] pb-6",
        ),
        rx.el.div(
            rx.el.h2(
                "Query your database.",
                class_name="text-2xl font-semibold tracking-tight text-[#172b42]",
            ),
            rx.el.p(
                "Choose a saved connection or enter your own, write a SELECT, and inspect the result — without saving passwords.",
                class_name="mt-2 text-sm leading-6 text-[#73808a]",
            ),
            class_name="py-7",
        ),
        rx.el.form(
            connection_panel(),
            editor_panel(),
            on_submit=QueryState.execute,
            class_name="grid w-full grid-cols-1 items-start gap-6 lg:grid-cols-[360px_minmax(0,1fr)]",
        ),
        results_panel(),
        mcp_connector(),
        rx.el.footer(
            rx.el.div(
                rx.icon("lock-keyhole", class_name="h-3.5 w-3.5"),
                rx.el.p(
                    "SQL passwords are used only for this execution; never saved or logged.",
                    class_name="text-xs",
                ),
                class_name="flex items-center gap-2 text-[#73808a]",
            ),
            rx.el.p(
                "SQL Server / pymssql only · Other engines require their own driver",
                class_name="text-[11px] text-[#8a9590]",
            ),
            class_name="flex flex-wrap items-center justify-between gap-3 py-5",
        ),
        class_name="relative z-10 mx-auto min-h-dvh w-full max-w-[1440px] px-5 py-7 font-['Inter'] text-[#172b42] sm:px-8 lg:px-12",
    )
