import reflex as rx

import os
from collections.abc import Sequence

import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState

_PROVIDER_NAME = os.environ.get("OIDC_PROVIDER_NAME", "")
_LOGIN_LABEL = (
    f"Continue with {_PROVIDER_NAME}" if _PROVIDER_NAME else "Sign in"
)


class LoginRedirectState(rx.State):
    @rxe.event(auth=False)
    def continue_to_app(self):
        raw = self.router.page.params.get("redirect_to", "/")
        target = (
            raw
            if isinstance(raw, str)
            and raw.startswith("/")
            and not raw.startswith("//")
            and not any(c in raw for c in "\t\r\n\\")
            else "/"
        )
        return rx.redirect(target)


def _login_buttons(providers: Sequence) -> list[rx.Component]:
    return [
        provider.get_login_button(
            rx.el.button(
                rx.icon("log-in", class_name="h-4 w-4"),
                _LOGIN_LABEL,
                class_name="flex w-full items-center justify-center gap-2 rounded-lg bg-[#16766b] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#105e55] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700",
            )
        )
        for provider in providers
    ]


def login_page(*, providers: Sequence, **context) -> rx.Component:
    return rx.fragment(
        rx.el.main(
            rx.el.div(
                rx.el.div(
                    rx.icon("database", class_name="h-6 w-6 text-white"),
                    class_name="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-xl bg-[#16766b]",
                ),
                rx.el.h1(
                    "SQL Workbench",
                    class_name="text-center text-2xl font-semibold tracking-tight text-[#172b42]",
                ),
                rx.el.p(
                    "A focused space for read-only exploration",
                    class_name="mt-2 text-center text-sm text-[#73808a]",
                ),
                rx.el.div(
                    rx.el.h2(
                        "Welcome to your workbench",
                        class_name="text-lg font-semibold text-[#172b42]",
                    ),
                    rx.el.p(
                        "Sign in with your Reflex account to access your private SQL Server connection profiles.",
                        class_name="mt-2 mb-6 text-sm leading-6 text-[#73808a]",
                    ),
                    *_login_buttons(providers),
                    rx.el.div(
                        rx.icon(
                            "shield-check",
                            class_name="h-4 w-4 shrink-0 text-teal-700",
                        ),
                        rx.el.p(
                            "Connection settings belong to you. SQL passwords are never saved and are required each time you run a query.",
                            class_name="text-xs leading-5 text-[#54716b]",
                        ),
                        class_name="mt-6 flex gap-3 rounded-lg border border-teal-900/10 bg-[#f0f7f4] p-4",
                    ),
                    class_name="mt-8 rounded-xl border border-[#dfe3df] bg-white p-6 sm:p-8",
                ),
                class_name="w-full max-w-md",
            ),
            class_name="flex min-h-dvh w-full items-center justify-center bg-[#f4f5f0] px-5 py-12 font-['Inter'] text-[#172b42]",
        ),
        rx.cond(
            AuthUserState.provider_name != "",
            rx.el.div(on_mount=LoginRedirectState.continue_to_app),
        ),
    )
