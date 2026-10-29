"""The Terminal window, from the Debug window: run a shell command on the Pi and read what it prints.

A command is typed on the screen keyboard (or a USB one), picked from the last ones, or run with one touch
from the quick commands. It runs in its own shell, in the folder that `cd` last chose; what it prints
shows as it comes, and Stop ends a long one (journalctl -f, say). It is not a full terminal: a command
that asks something while it runs (vim, top, a sudo password) gets no answer.
Only for the display: the page offers it only when it is opened on the Pi itself.
"""

import asyncio
import contextlib
import html
import os
import re
import shlex
import signal
import time
from dataclasses import dataclass
from pathlib import Path

from nicegui import ui

from frontend.controls import Target
from frontend.keyboard import Keyboard
from frontend.targets import Reachable, button, usable
from shared.config import ROOT

MAX_LINES = 400  # of output kept: the older ones go
DRAW_PERIOD = 0.1  # s: a command that prints a lot redraws the output at most this often
STOP_GRACE = 2.0  # s a stopped command has to end before it is killed
HISTORY = 5  # last commands offered on the keyboard
SCROLL_STEP = 60  # px of output per step of the encoder
SCROLL = "terminal output"  # the setting the encoder turns when the frame is on the output
# colors and cursor moves: the screen shows plain text
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
HINT = "Pick a quick command, or type one: it runs on the Pi, in this folder."
SHELL_KEYS = "-/.|"  # on the keyboard beside the space bar: shell commands are full of them

# one touch, for what is looked at most often on the handcart
QUICK = [
    ("Backend log", "journalctl -u handcart-backend -n 100 --no-pager"),
    ("Status", f"{shlex.quote(str(ROOT / 'handcart.py'))} status"),
    ("CAN", "ip -details -statistics link show can0"),
    ("Network", "ip -brief address"),
    ("Disk", "df -h /"),
]

# What each kind of line is, for its color (CSS .t-*): the command run, what it printed on stdout and on
# stderr, and how it ended
COMMAND, OUT, ERR, FAILED, STOPPED = "cmd", "out", "err", "fail", "stop"


@dataclass(frozen=True)
class Line:
    kind: str
    text: str
    prompt: str = ""  # of a command: where it was typed (a cd changes it)


class TerminalWindow:
    def __init__(self) -> None:
        self._client = ui.context.client
        self._folder = ROOT
        self._lines: list[Line] = []
        self._history: list[str] = []  # the last commands, the newest first
        self._process: asyncio.subprocess.Process | None = None
        self._running = ""  # the command running, for the title
        self._started = 0.0  # when it started
        self._drawn_at = 0.0

        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet term"):
            with ui.element("div") as self._output_view:
                with ui.element("div").classes("thead"):
                    ui.label("Terminal").classes("sheet-title")
                    self._where = ui.label("").classes("sheet-sub num")
                with ui.element("div").classes("tchips"):
                    self._quick = []
                    for label, command in QUICK:
                        chip = ui.button(label, on_click=lambda command=command: self._execute(command))
                        chip.props("flat no-caps text-color=white").classes("tchip")
                        self._quick.append(chip)
                # column-reverse: it stays scrolled to the end
                with ui.element("div").classes("tout").props("id=terminal-output") as self._output_box:
                    self._output = ui.html("").classes("ttext num")
                with ui.element("div").classes("sheet-actions tacts"):
                    self._close = ui.button("Close", on_click=lambda: self.root.set_visibility(False))
                    self._close.props("flat no-caps text-color=white").classes("cancel")
                    self._stop = ui.button("Stop", icon="stop", on_click=self._on_stop)
                    self._stop.props("unelevated no-caps color=negative")
                    self._type = ui.button("Type a command", icon="keyboard", on_click=self._show_keyboard)
                    self._type.props("unelevated no-caps text-color=black")

            with ui.element("div") as self._keyboard_view:
                with ui.element("div").classes("tchips"):
                    self._recent = []
                    for i in range(HISTORY):
                        chip = ui.button("", on_click=lambda i=i: self._pick(i))
                        chip.props("flat no-caps text-color=white").classes("tchip num")
                        self._recent.append(chip)
                self._keyboard = Keyboard(secret=False, extra=SHELL_KEYS)
                with ui.element("div").classes("sheet-actions"):
                    self._cancel = ui.button("Cancel", on_click=self._show_output)
                    self._cancel.props("flat no-caps text-color=white").classes("cancel")
                    self._run_button = ui.button("Run", icon="play_arrow", on_click=self._on_run)
                    self._run_button.props("unelevated no-caps text-color=black")
        self.root.set_visibility(False)
        self._keyboard_view.set_visibility(False)
        self._client.on_disconnect(self._kill)  # the page is gone: so is what it started
        ui.timer(1.0, self._draw_title)  # the seconds of the command running
        self._draw()

    def reachable(self) -> list[Reachable]:
        if self._keyboard_view.visible:
            recent = usable(*[button(f"recent {i}", chip) for i, chip in enumerate(self._recent)])
            actions = usable(button("cancel", self._cancel), button("run", self._run_button, priority=1))
            return [*recent, *self._keyboard.reachable(), *actions]
        quick = usable(*[button(f"quick {i}", chip) for i, chip in enumerate(self._quick)])
        # on the output the encoder scrolls it, and a click opens the keyboard
        output = Reachable(Target("output", adjusts=SCROLL, presses="type"), self._output_box, lambda: None)
        actions = usable(
            button("close", self._close),
            button("stop", self._stop, priority=1),
            button("type", self._type, priority=1),
        )
        return [*quick, output, *actions]

    def open(self) -> None:
        self._show_output()
        self.root.set_visibility(True)

    def typing(self) -> bool:
        """Whether the screen keyboard is open: a USB keyboard types into it (on_key)."""
        return self.root.visible and self._keyboard_view.visible

    async def on_key(self, key: str) -> None:
        """A key of a USB keyboard while typing: Enter runs, Escape goes back, the rest types."""
        if key == "Enter":
            await self._on_run()
        elif key == "Escape":
            self._show_output()
        else:
            self._keyboard.press_key(key)

    def scroll(self, steps: int) -> None:
        """Turning the encoder on the output: clockwise towards the newest lines."""
        self._client.run_javascript(
            f"document.getElementById('terminal-output')?.scrollBy(0, {steps * SCROLL_STEP})"
        )

    # views

    def _show_output(self) -> None:
        self._keyboard_view.set_visibility(False)
        self._output_view.set_visibility(True)
        self._draw()

    def _show_keyboard(self) -> None:
        self._keyboard.clear(self._prompt())
        for i, chip in enumerate(self._recent):
            chip.set_visibility(i < len(self._history))
            if i < len(self._history):
                chip.set_text(self._history[i])
        self._output_view.set_visibility(False)
        self._keyboard_view.set_visibility(True)

    def _pick(self, i: int) -> None:
        """One of the last commands into the field, to run again or to fix."""
        if i < len(self._history):
            self._keyboard.clear(self._prompt(), self._history[i])

    # commands

    async def _on_run(self) -> None:
        command = self._keyboard.text.strip()
        self._show_output()
        if command:
            self._remember(command)
            await self._execute(command)

    def _remember(self, command: str) -> None:
        if command in self._history:
            self._history.remove(command)
        self._history.insert(0, command)
        del self._history[HISTORY:]

    async def _execute(self, command: str) -> None:
        if self._process is not None:
            return  # one at a time
        self._lines.append(Line(COMMAND, command, self._prompt()))
        if command == "cd" or command.startswith("cd "):
            self._change_folder(command[2:].strip())
        else:
            await self._run(command)
        self._draw()

    def _change_folder(self, target: str) -> None:
        folder = (self._folder / Path(target or "~").expanduser()).resolve()
        if folder.is_dir():
            self._folder = folder
        else:
            self._add(ERR, f"cd: no such folder: {target}")

    async def _run(self, command: str) -> None:
        """Run the command in a shell, adding what it prints as it comes."""
        self._process = await asyncio.create_subprocess_shell(
            command,
            cwd=self._folder,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,  # apart: its lines show in red
            start_new_session=True,  # its own process group: Stop ends its children too
            env={**os.environ, "TERM": "dumb"},
        )
        self._running, self._started = command, time.monotonic()
        self._draw()
        assert self._process.stdout is not None and self._process.stderr is not None
        await asyncio.gather(self._read(self._process.stdout, OUT), self._read(self._process.stderr, ERR))
        code = await self._process.wait()
        self._process = None
        if code < 0:
            self._add(STOPPED, "[stopped]")  # ended by a signal: Stop
        elif code != 0:
            self._add(FAILED, f"[exit {code}]")

    async def _read(self, stream: asyncio.StreamReader, kind: str) -> None:
        async for raw in stream:
            self._add(kind, ANSI_ESCAPE.sub("", raw.decode(errors="replace").rstrip("\r\n")))
            if time.monotonic() - self._drawn_at >= DRAW_PERIOD:
                self._draw()

    async def _on_stop(self) -> None:
        process = self._process
        if process is None:
            return
        self._signal(process, signal.SIGTERM)
        await asyncio.sleep(STOP_GRACE)
        if process.returncode is None:
            self._signal(process, signal.SIGKILL)

    def _kill(self) -> None:
        if self._process is not None:
            self._signal(self._process, signal.SIGKILL)

    def _signal(self, process: asyncio.subprocess.Process, sig: int) -> None:
        with contextlib.suppress(ProcessLookupError):  # it ended meanwhile
            os.killpg(process.pid, sig)

    # drawing

    def _add(self, kind: str, text: str) -> None:
        self._lines.append(Line(kind, text))
        del self._lines[:-MAX_LINES]

    def _draw(self) -> None:
        self._drawn_at = time.monotonic()
        self._draw_title()
        # escaped: what a command prints is text, never HTML for the display
        rows = []
        for line in self._lines:
            text = html.escape(line.text)
            if line.kind == COMMAND:
                rows.append(f'<div class="t-cmd"><span>{html.escape(line.prompt)}</span> {text}</div>')
            else:
                rows.append(f'<div class="t-{line.kind}">{text or " "}</div>')
        self._output.set_content("".join(rows) or f'<div class="t-hint">{HINT}</div>')
        running = self._process is not None
        self._stop.set_visibility(running)
        self._type.set_visibility(not running)
        for chip in self._quick:
            chip.set_enabled(not running)

    def _draw_title(self) -> None:
        """The folder; while a command runs, the command and for how long."""
        if self._process is not None:
            seconds = time.monotonic() - self._started
            self._where.set_text(f"Running {self._running} · {seconds:.0f} s")
            self._where.classes(add="running")
        else:
            self._where.set_text(self._path())
            self._where.classes(remove="running")

    def _prompt(self) -> str:
        """Short, as in a shell: the folder's name. The whole path is in the title."""
        return f"{self._folder.name or '/'} $"

    def _path(self) -> str:
        home = Path.home()
        if self._folder.is_relative_to(home):
            return "~/" + str(self._folder.relative_to(home))
        return str(self._folder)
