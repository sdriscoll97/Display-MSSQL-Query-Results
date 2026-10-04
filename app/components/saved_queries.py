import reflex as rx

from app.states.query_state import QueryState
from app.states.saved_query_state import SavedQueryState


SAVE_QUERY_SCRIPT = "(() => ({query_name: document.getElementById('query_name')?.value || '', sql: document.getElementById('sql')?.value || '', associate: document.getElementById('query_associate')?.checked === true}))()"
EXPORT_SCRIPT = "(() => { const fields = ['host','port','database','username','sql','password']; const data = Object.fromEntries(fields.map(name => [name, document.getElementById(name)?.value || ''])); const password = document.getElementById('password'); if (password) password.value = ''; return data; })()"


def saved_queries() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "Your saved queries",
                class_name="text-xs font-semibold text-[#26364b]",
            ),
            rx.el.button(
                rx.icon("refresh-cw", class_name="h-3.5 w-3.5"),
                type="button",
                title="Refresh saved queries",
                on_click=SavedQueryState.load_queries,
                class_name="rounded p-1 text-teal-700 hover:bg-teal-50",
            ),
            class_name="flex items-center justify-between",
        ),
        rx.el.div(
            rx.el.button(
                "Ad-hoc / new query",
                type="button",
                on_click=SavedQueryState.ad_hoc,
                disabled=(QueryState.status == "loading")
                | QueryState.export_loading,
                class_name=rx.cond(
                    SavedQueryState.selected_id == 0,
                    "rounded-lg border border-teal-700 bg-teal-50 px-3 py-2 text-left text-xs text-teal-800",
                    "rounded-lg border border-[#dce0df] bg-white px-3 py-2 text-left text-xs text-[#26364b] hover:bg-stone-50",
                ),
            ),
            rx.foreach(
                SavedQueryState.queries,
                lambda item: rx.el.button(
                    rx.icon("file-code", class_name="h-3.5 w-3.5 shrink-0"),
                    rx.el.span(item["name"], class_name="truncate"),
                    type="button",
                    key=item["id"],
                    title=item["name"],
                    on_click=SavedQueryState.select_query(item["id"]),
                    disabled=(QueryState.status == "loading")
                    | QueryState.export_loading,
                    class_name=rx.cond(
                        SavedQueryState.selected_id == item["id"],
                        "flex items-center gap-2 rounded-lg border border-teal-700 bg-teal-50 px-3 py-2 text-left text-xs text-teal-800",
                        "flex items-center gap-2 rounded-lg border border-[#dce0df] bg-white px-3 py-2 text-left text-xs text-[#26364b] hover:bg-stone-50",
                    ),
                ),
            ),
            class_name="mt-3 flex max-h-40 flex-col gap-2 overflow-y-auto",
        ),
        rx.cond(
            SavedQueryState.queries.length() == 0,
            rx.el.p(
                "No saved queries on this page. Save your SELECT below.",
                class_name="mt-2 text-xs text-[#73808a]",
            ),
        ),
        rx.el.div(
            rx.el.button(
                "Previous",
                type="button",
                on_click=SavedQueryState.previous_page,
                disabled=SavedQueryState.page_offset == 0,
                class_name="text-xs text-teal-700 disabled:text-stone-400",
            ),
            rx.el.button(
                "Next",
                type="button",
                on_click=SavedQueryState.next_page,
                disabled=~SavedQueryState.has_more,
                class_name="text-xs text-teal-700 disabled:text-stone-400",
            ),
            class_name="mt-2 flex justify-between",
        ),
        rx.el.label(
            "Query name",
            html_for="query_name",
            class_name="mb-2 mt-4 block text-xs font-semibold text-[#26364b]",
        ),
        rx.el.input(
            id="query_name",
            name="query_name",
            default_value=SavedQueryState.name,
            key=SavedQueryState.name,
            max_length=200,
            placeholder="e.g. Monthly reporting",
            class_name="h-10 w-full rounded-lg border border-[#dce0df] bg-white px-3 text-sm text-[#172b42] outline-hidden focus:border-teal-600",
        ),
        rx.el.label(
            rx.el.input(
                id="query_associate",
                name="query_associate",
                type="checkbox",
                default_checked=SavedQueryState.associated,
                key=f"{SavedQueryState.selected_id}-{SavedQueryState.associated}",
                class_name="accent-teal-700",
            ),
            "Associate with selected saved connection profile",
            class_name="mt-3 flex items-center gap-2 text-xs text-[#26364b]",
        ),
        rx.el.div(
            rx.el.button(
                rx.icon("save", class_name="h-3.5 w-3.5"),
                rx.cond(
                    SavedQueryState.selected_id > 0,
                    "Update query",
                    "Save query",
                ),
                type="button",
                on_click=rx.call_script(
                    SAVE_QUERY_SCRIPT, callback=SavedQueryState.save_query
                ),
                disabled=(QueryState.status == "loading")
                | QueryState.export_loading,
                class_name="flex items-center gap-2 rounded-lg bg-[#16766b] px-3 py-2 text-xs font-semibold text-white hover:bg-[#105e55] disabled:bg-stone-400",
            ),
            rx.cond(
                SavedQueryState.selected_id > 0,
                rx.el.button(
                    rx.icon("trash-2", class_name="h-3.5 w-3.5"),
                    "Delete",
                    type="button",
                    on_click=SavedQueryState.ask_delete,
                    class_name="flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs text-red-600 hover:bg-red-50",
                ),
            ),
            class_name="mt-3 flex gap-2",
        ),
        rx.cond(
            SavedQueryState.delete_pending,
            rx.el.div(
                rx.el.p(
                    f"Delete {SavedQueryState.name}? This cannot be undone.",
                    class_name="text-xs text-red-700",
                ),
                rx.el.div(
                    rx.el.button(
                        "Confirm delete",
                        type="button",
                        on_click=SavedQueryState.delete_query,
                        class_name="rounded-lg bg-red-600 px-3 py-2 text-xs text-white hover:bg-red-700",
                    ),
                    rx.el.button(
                        "Cancel",
                        type="button",
                        on_click=SavedQueryState.cancel_delete,
                        class_name="rounded-lg border border-[#dce0df] bg-white px-3 py-2 text-xs text-[#26364b]",
                    ),
                    class_name="mt-2 flex gap-2",
                ),
                class_name="mt-3 rounded-lg border border-red-200 bg-red-50 p-3",
            ),
        ),
        rx.cond(
            SavedQueryState.error != "",
            rx.el.p(
                SavedQueryState.error,
                role="alert",
                class_name="mt-3 text-xs text-red-600",
            ),
        ),
        rx.cond(
            SavedQueryState.message != "",
            rx.el.p(
                SavedQueryState.message,
                role="status",
                class_name="mt-3 text-xs text-teal-700",
            ),
        ),
        class_name="mb-5 border-b border-[#e8e9e5] pb-5",
    )


def csv_export() -> rx.Component:
    return rx.el.div(
        rx.el.button(
            rx.cond(
                QueryState.export_loading,
                rx.icon("loader-circle", class_name="h-4 w-4 animate-spin"),
                rx.icon("download", class_name="h-4 w-4"),
            ),
            rx.cond(
                QueryState.export_loading, "Exporting…", "Export all rows · CSV"
            ),
            type="button",
            on_click=rx.call_script(
                EXPORT_SCRIPT, callback=QueryState.export_csv
            ),
            disabled=(QueryState.status == "loading")
            | QueryState.export_loading,
            class_name="flex items-center gap-2 rounded-lg border border-teal-700 bg-white px-4 py-3 text-sm font-semibold text-teal-800 hover:bg-teal-50 disabled:cursor-wait disabled:text-stone-400",
        ),
        rx.el.p(
            "Re-runs the current SELECT with a fresh password. No export row, column or value cap; TOP/filters in your SQL still apply. Results may change since preview. CSV text is formula-safe; NULL is empty and binary is hex. Download available for 2 minutes.",
            class_name="mt-3 text-xs leading-5 text-[#73808a]",
        ),
        rx.cond(
            QueryState.export_loading,
            rx.el.p(
                f"{QueryState.export_rows:,} rows written…",
                role="status",
                class_name="mt-2 font-mono text-xs text-teal-700",
            ),
        ),
        rx.cond(
            QueryState.export_message != "",
            rx.el.p(
                QueryState.export_message,
                role="status",
                class_name="mt-2 text-xs text-teal-700",
            ),
        ),
        rx.cond(
            QueryState.export_error != "",
            rx.el.p(
                QueryState.export_error,
                role="alert",
                class_name="mt-2 text-xs text-red-600",
            ),
        ),
        class_name="mt-5 border-t border-[#e8e9e5] pt-5",
    )
