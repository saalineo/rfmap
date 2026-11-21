from PyQt6.QtWidgets import QStatusBar


class SurveyStatusBar(QStatusBar):
    """Short, actionable feedback for the active survey step."""

    def show_hint(self, message: str):
        self.showMessage(message)
