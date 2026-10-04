import reflex as rx

import reflex_enterprise as rxe


class AppearanceState(rx.State):
    evil_eye_enabled: bool = False

    @rxe.event
    def toggle_evil_eye(self):
        self.evil_eye_enabled = not self.evil_eye_enabled
