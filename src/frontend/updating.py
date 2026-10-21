"""The whole screen while ./handcart.py update runs, and a note on how it ended."""

from nicegui import ui

from frontend import local_files
from frontend.overlays import Toast

WARNING_TIME = 20.0  # s the "boot files changed" note stays: long enough to read and act on


class Updating:
    def __init__(self, toast: Toast) -> None:
        self._toast = toast
        self._was_updating = False  # to tell how the update ended, once it is over
        with ui.element("div").classes("updating") as self.root:  # above everything, the offline screen too
            ui.element("div").classes("eagle")
            ui.label("Updating").classes("ut")
            self._step = ui.label("").classes("us")
            ui.label("Do not switch the handcart off. The screen goes blank for a moment while it restarts.")
        self.root.set_visibility(False)

    def refresh(self) -> None:
        """While the update runs, its step; when it ends, a note with how it went."""
        step = local_files.update_step()
        self.root.set_visibility(step != "")
        self._step.set_text(step)
        if step:
            self._was_updating = True
        elif self._was_updating:
            self._was_updating = False
            self._tell_result(local_files.last_update())

    def _tell_result(self, result: str) -> None:
        ok = "fail" not in result and "Not updated" not in result
        if "by hand" in result:  # BOOT_CHANGED in handcart.py: something to do on the Pi by hand
            self._toast.show(result, ok=ok, seconds=WARNING_TIME, warning=True)
        else:
            self._toast.show(result or "Update finished", ok=ok)
