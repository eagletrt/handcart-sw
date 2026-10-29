"""The System window, behind the gear in the top bar: version, updates, terminal, reboot and shut down."""

import html
from collections.abc import Awaitable, Callable

from nicegui import ui

from frontend.backend import Backend
from frontend.overlays import ConfirmWindow
from frontend.targets import Reachable, button, usable
from shared.models import SystemInfo

COMMITS_SHOWN = 4  # the rest is "+ N more"


class SystemWindow:
    def __init__(
        self,
        backend: Backend,
        confirm: ConfirmWindow,
        report: Callable[[str], None],
        open_terminal: Callable[[], None] | None,  # None: no terminal (the page is not on the Pi itself)
    ) -> None:
        self._backend = backend
        self._open_terminal = open_terminal
        self._confirm = confirm
        self._report = report  # shows why something was refused

        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet sys"):
            ui.label("System").classes("sheet-title")
            self._version = ui.label("").classes("sheet-sub num")
            self._last_update = ui.label("").classes("sheet-sub")
            with ui.element("div").classes("updates"):
                self._updates_title = ui.label("").classes("ut")
                self._commits = ui.html("").classes("commits num")
                with ui.element("div").classes("ubtns"):
                    self._check = ui.button("Check for updates", icon="refresh", on_click=self._on_check)
                    self._check.props("flat no-caps text-color=white").classes("cancel")
                    self._update_button = ui.button(
                        "Update & restart", icon="system_update", on_click=self._on_update
                    )
                    self._update_button.props("unelevated no-caps text-color=black")
            self._handcart_only = ui.label("Update, reboot and shut down work only on the handcart").classes(
                "sheet-sub"
            )
            with ui.element("div").classes("sheet-actions power"):
                self._close = ui.button("Close", on_click=lambda: self.root.set_visibility(False))
                self._close.props("flat no-caps text-color=white").classes("cancel")
                self._terminal = ui.button("Terminal", icon="terminal", on_click=self._on_terminal)
                self._terminal.props("flat no-caps text-color=white").classes("cancel")
                self._terminal.set_visibility(open_terminal is not None)
                self._reboot = ui.button("Reboot", icon="restart_alt", on_click=self._on_reboot)
                self._reboot.props("flat no-caps text-color=white").classes("cancel")
                self._shut_down = ui.button(
                    "Shut down", icon="power_settings_new", on_click=self._on_shut_down
                )
                self._shut_down.props("unelevated no-caps color=negative")
        self.root.set_visibility(False)

    def reachable(self) -> list[Reachable]:
        return usable(
            button("check", self._check),
            button("update", self._update_button),
            button("close", self._close, priority=1),
            button("terminal", self._terminal),
            button("reboot", self._reboot),
            button("shut down", self._shut_down),
        )

    def open(self) -> None:
        self.update()
        self.root.set_visibility(True)

    def update(self) -> None:
        """Draw what the backend last said about the system."""
        info = self._backend.system
        if info is None:
            self._version.set_text("Reading the version…")
            return
        self._version.set_text(f"Version {info.version} · branch {info.branch}")
        self._last_update.set_visibility(info.last_update is not None)
        self._last_update.set_text(f"Last update: {info.last_update}")
        self._handcart_only.set_visibility(not info.on_handcart)
        self._draw_updates(info)

    def _draw_updates(self, info: SystemInfo) -> None:
        count = len(info.updates)
        if info.checked_at is None:
            self._updates_title.set_text("Not checked yet")
        elif info.check_problem:
            self._updates_title.set_text(info.check_problem)
        elif count == 0:
            self._updates_title.set_text(f"Up to date · checked {info.checked_at}")
        elif count == 1:
            self._updates_title.set_text("1 update")
        else:
            self._updates_title.set_text(f"{count} updates")

        # escaped: a commit message is text written by anyone who can push, never HTML for the display
        lines = [f"<div>{html.escape(commit)}</div>" for commit in info.updates[:COMMITS_SHOWN]]
        if count > COMMITS_SHOWN:
            lines.append(f"<div>+ {count - COMMITS_SHOWN} more</div>")
        self._commits.set_content("".join(lines))
        self._update_button.set_visibility(count > 0)

    # buttons

    async def _on_check(self) -> None:
        self._updates_title.set_text("Checking…")
        problem = await self._backend.check_updates()
        if problem:
            self._report(problem)
        self.update()

    def _on_update(self) -> None:
        self._confirm.ask(
            "Update and restart?",
            "The screen shows each step, and goes blank for a moment when it restarts. If the new "
            "version does not start, the handcart goes back to this one by itself.",
            "Update",
            lambda: self._run(self._backend.update),
        )

    def _on_terminal(self) -> None:
        if self._open_terminal is not None:
            self.root.set_visibility(False)
            self._open_terminal()

    def _on_reboot(self) -> None:
        self._confirm.ask(
            "Reboot the handcart?",
            "It is back in about a minute.",
            "Reboot",
            lambda: self._run(self._backend.reboot),
        )

    def _on_shut_down(self) -> None:
        self._confirm.ask(
            "Shut down the handcart?",
            "To turn it on again, switch the power off and on.",
            "Shut down",
            lambda: self._run(self._backend.shut_down),
        )

    async def _run(self, action: Callable[[], Awaitable[str | None]]) -> None:
        """Ask the backend; on a refusal say why, else close (the screen is about to go)."""
        problem = await action()
        if problem:
            self._report(problem)
        else:
            self.root.set_visibility(False)
