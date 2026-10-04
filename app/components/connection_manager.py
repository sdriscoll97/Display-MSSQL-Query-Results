import reflex as rx

from app.states.connection_state import ConnectionState
from app.states.query_state import QueryState


def connection_manager() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(
                "Your saved profiles",
                class_name="text-xs font-semibold text-[#26364b]",
            ),
            rx.el.button(
                rx.icon("refresh-cw", class_name="h-3.5 w-3.5"),
                type="button",
                title="Refresh profiles",
                on_click=ConnectionState.load_profiles,
                class_name="rounded p-1 text-teal-700 hover:bg-teal-50",
            ),
            class_name="flex items-center justify-between",
        ),
        rx.el.div(
            rx.el.button(
                "Ad-hoc / new profile",
                type="button",
                on_click=ConnectionState.new_connection,
                disabled=(QueryState.status == "loading")
                | QueryState.export_loading,
                class_name=rx.cond(
                    ConnectionState.selected_id == 0,
                    "w-full rounded-lg border border-teal-700 bg-teal-50 px-3 py-2 text-left text-xs font-medium text-teal-800",
                    "w-full rounded-lg border border-[#dce0df] bg-white px-3 py-2 text-left text-xs text-[#26364b] hover:bg-stone-50",
                ),
            ),
            rx.foreach(
                ConnectionState.profiles,
                lambda profile: rx.el.button(
                    rx.icon("database", class_name="h-3.5 w-3.5 shrink-0"),
                    rx.el.span(profile["name"], class_name="truncate"),
                    type="button",
                    key=profile["id"],
                    title=profile["name"],
                    on_click=ConnectionState.select_profile(profile["id"]),
                    disabled=QueryState.status == "loading",
                    class_name=rx.cond(
                        ConnectionState.selected_id == profile["id"],
                        "flex w-full items-center gap-2 rounded-lg border border-teal-700 bg-teal-50 px-3 py-2 text-left text-xs text-teal-800",
                        "flex w-full items-center gap-2 rounded-lg border border-[#dce0df] bg-white px-3 py-2 text-left text-xs text-[#26364b] hover:bg-stone-50",
                    ),
                ),
            ),
            class_name="mt-3 flex max-h-48 flex-col gap-2 overflow-y-auto",
        ),
        rx.cond(
            ConnectionState.profiles.length() == 0,
            rx.el.p(
                "No saved profiles on this page. Save your first connection below.",
                class_name="mt-2 text-xs leading-5 text-[#73808a]",
            ),
        ),
        rx.cond(
            (ConnectionState.page_offset > 0) | ConnectionState.has_more,
            rx.el.div(
                rx.el.button(
                    "Previous",
                    type="button",
                    on_click=ConnectionState.previous_page,
                    disabled=ConnectionState.page_offset == 0,
                    class_name="text-xs text-teal-700 disabled:text-stone-400",
                ),
                rx.el.button(
                    "Next",
                    type="button",
                    on_click=ConnectionState.next_page,
                    disabled=~ConnectionState.has_more,
                    class_name="text-xs text-teal-700 disabled:text-stone-400",
                ),
                class_name="mt-2 flex justify-between",
            ),
        ),
        rx.el.div(
            rx.el.label(
                "Profile name",
                html_for="profile_name",
                class_name="mb-2 block text-xs font-semibold text-[#26364b]",
            ),
            rx.el.input(
                id="profile_name",
                name="profile_name",
                default_value=ConnectionState.name,
                key=ConnectionState.name,
                max_length=200,
                placeholder="e.g. Reporting · read-only",
                auto_complete="off",
                disabled=QueryState.status == "loading",
                class_name="h-11 w-full rounded-lg border border-[#dce0df] bg-white px-3 text-sm text-[#172b42] outline-hidden focus:border-teal-600 focus:ring-2 focus:ring-teal-600/10",
            ),
            class_name="mt-4",
        ),
        rx.cond(
            ConnectionState.selected_id > 0,
            rx.el.p(
                "Edit fields and save to update this profile. Execution uses its saved settings; choose ad-hoc mode to run unsaved details.",
                class_name="mt-2 text-xs leading-5 text-[#73808a]",
            ),
        ),
        rx.el.div(
            rx.el.button(
                rx.icon("save", class_name="h-3.5 w-3.5"),
                rx.cond(
                    ConnectionState.selected_id > 0,
                    "Save changes",
                    "Save profile",
                ),
                type="button",
                disabled=QueryState.status == "loading",
                on_click=rx.call_script(
                    "(() => { const fields = ['profile_name', 'host', 'port', 'database', 'username']; return Object.fromEntries(fields.map(name => [name, document.getElementById(name)?.value || ''])); })()",
                    callback=ConnectionState.save_profile,
                ),
                class_name="flex items-center gap-2 rounded-lg bg-[#16766b] px-3 py-2 text-xs font-semibold text-white hover:bg-[#105e55] disabled:bg-stone-400",
            ),
            rx.cond(
                ConnectionState.selected_id > 0,
                rx.el.button(
                    rx.icon("trash-2", class_name="h-3.5 w-3.5"),
                    "Delete",
                    type="button",
                    on_click=ConnectionState.ask_delete,
                    disabled=QueryState.status == "loading",
                    class_name="flex items-center gap-2 rounded-lg border border-red-200 bg-white px-3 py-2 text-xs text-red-600 hover:bg-red-50",
                ),
            ),
            class_name="mt-3 flex flex-wrap gap-2",
        ),
        rx.cond(
            ConnectionState.delete_pending,
            rx.el.div(
                rx.el.p(
                    f"Delete {ConnectionState.name}? This cannot be undone.",
                    class_name="text-xs leading-5 text-red-700",
                ),
                rx.el.div(
                    rx.el.button(
                        "Confirm delete",
                        type="button",
                        on_click=ConnectionState.delete_profile,
                        class_name="rounded-lg bg-red-600 px-3 py-2 text-xs text-white hover:bg-red-700",
                    ),
                    rx.el.button(
                        "Cancel",
                        type="button",
                        on_click=ConnectionState.cancel_delete,
                        class_name="rounded-lg border border-[#dce0df] bg-white px-3 py-2 text-xs text-[#26364b]",
                    ),
                    class_name="mt-2 flex gap-2",
                ),
                class_name="mt-3 rounded-lg border border-red-200 bg-red-50 p-3",
            ),
        ),
        rx.cond(
            ConnectionState.error != "",
            rx.el.p(
                ConnectionState.error,
                role="alert",
                class_name="mt-3 text-xs leading-5 text-red-600",
            ),
        ),
        rx.cond(
            ConnectionState.message != "",
            rx.el.p(
                ConnectionState.message,
                role="status",
                class_name="mt-3 text-xs leading-5 text-teal-700",
            ),
        ),
        class_name="mb-5 border-b border-[#e8e9e5] pb-5",
    )
