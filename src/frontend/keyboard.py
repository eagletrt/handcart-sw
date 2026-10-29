"""A keyboard on the screen, for the Wi-Fi password and the terminal: the handcart has no keyboard.

Touch the keys. With the physical controls the frame moves over them like over any other button, and the
click types the framed key: slow, but it works without touching the screen.
"""

from nicegui import ui

from frontend.targets import Reachable, button, usable

DIGITS = "1234567890"
LETTERS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
SYMBOLS = ["@#$%&*-+=/", "!?.,:;_~'", '"()<>\\|']  # the same lengths as LETTERS: they use the same keys
HIDDEN = "•"
LAST_CHAR_TIME = 1.0  # s the last character typed stays readable, as on a phone
VISIBLE_CHARS = 44  # of a text that is not secret: a longer one shows its end, where the typing is


class Keyboard:
    def __init__(self, secret: bool = True, extra: str = "") -> None:
        """extra: symbols worth a key of their own, beside the space bar ("-/.|" for shell commands)."""
        self.text = ""
        self._secret = secret  # a password: dots, with a button to show it
        self._caps = False  # capital letters, until shift is pressed again
        self._symbols = False  # the letter keys show symbols
        self._shown = False  # the text is shown, not dots
        self._last_readable = False  # the last character is shown, for LAST_CHAR_TIME after typing it

        with ui.element("div").classes("kb") as self.root:
            with ui.element("div").classes("kbfield"):
                self._label = ui.label("").classes("kblabel")  # what is typed: "Password of Eagle"
                self._field = ui.label("").classes("kbtext num")
                self._show = ui.button(icon="visibility", on_click=self._on_show)
                self._show.props("flat text-color=white").classes("kbkey")
                self._show.set_visibility(secret)
            self._digit_keys = self._row(DIGITS)
            self._letter_keys = []  # the keys of LETTERS (or SYMBOLS), row by row
            for row, letters in enumerate(LETTERS):
                with ui.element("div").classes(f"kbrow r{row}"):
                    if row == 2:
                        self._shift = ui.button(icon="arrow_upward", on_click=self._on_shift)
                        self._shift.props("flat text-color=white").classes("kbkey wide")
                    keys = []
                    for _ in letters:
                        key = ui.button("").props("flat no-caps text-color=white").classes("kbkey")
                        key.on_click(lambda key=key: self._type(key.text))
                        keys.append(key)
                    self._letter_keys.append(keys)
                    if row == 2:
                        self._delete = ui.button(icon="backspace", on_click=self._on_delete)
                        self._delete.props("flat text-color=white").classes("kbkey wide")
            with ui.element("div").classes("kbrow"):
                self._mode = ui.button("#+=", on_click=self._on_mode)
                self._mode.props("flat no-caps text-color=white").classes("kbkey wide")
                self._extra_keys = []
                for char in extra:
                    key = ui.button(char, on_click=lambda char=char: self._type(char))
                    key.props("flat no-caps text-color=white").classes("kbkey")
                    self._extra_keys.append(key)
                self._space = ui.button("space", on_click=lambda: self._type(" "))
                self._space.props("flat no-caps text-color=white").classes("kbkey space")
        self._draw()

    def reachable(self) -> list[Reachable]:
        """Every key that can be used, in reading order."""
        keys = [button("show", self._show)] if self._secret else []
        for i, key in enumerate(self._digit_keys):
            keys.append(button(f"digit {i}", key))
        for row, row_keys in enumerate(self._letter_keys):
            if row == 2:
                keys.append(button("shift", self._shift))
            for i, key in enumerate(row_keys):
                keys.append(button(f"key {row} {i}", key))
            if row == 2:
                keys.append(button("delete", self._delete))
        keys.append(button("mode", self._mode))
        for i, key in enumerate(self._extra_keys):
            keys.append(button(f"extra {i}", key))
        keys.append(button("space", self._space))
        return usable(*keys)

    def clear(self, label: str, text: str = "") -> None:
        """Start again with label next to the text, and this text already typed."""
        self._label.set_text(label)
        self.text = text
        self._caps = False
        self._symbols = False
        self._shown = False
        self._draw()

    def press_key(self, key: str) -> None:
        """A key of a USB keyboard (handcart.js): a character, or Backspace."""
        if key == "Backspace":
            self._on_delete()
        elif len(key) == 1:
            self._type(key)

    def _row(self, chars: str) -> list[ui.button]:
        """A row of keys that always type the same characters."""
        keys = []
        with ui.element("div").classes("kbrow"):
            for char in chars:
                key = ui.button(char, on_click=lambda char=char: self._type(char))
                key.props("flat no-caps text-color=white").classes("kbkey")
                keys.append(key)
        return keys

    def _type(self, char: str) -> None:
        self.text += char
        self._last_readable = True
        self._draw_field()
        with self.root:
            ui.timer(LAST_CHAR_TIME, self._hide_last, once=True)

    def _hide_last(self) -> None:
        # a later key starts its own timer: this one ends early, and the later one hides the char again
        self._last_readable = False
        self._draw_field()

    def _on_delete(self) -> None:
        self.text = self.text[:-1]
        self._last_readable = False
        self._draw_field()

    def _on_shift(self) -> None:
        self._caps = not self._caps
        self._draw()

    def _on_mode(self) -> None:
        self._symbols = not self._symbols
        self._draw()

    def _on_show(self) -> None:
        self._shown = not self._shown
        self._draw_field()

    def _draw(self) -> None:
        """The letter keys as letters (small or capital) or as symbols, and the field."""
        if self._symbols:
            rows = SYMBOLS
            self._mode.set_text("abc")
        elif self._caps:
            rows = [letters.upper() for letters in LETTERS]
            self._mode.set_text("#+=")
        else:
            rows = LETTERS
            self._mode.set_text("#+=")
        for chars, keys in zip(rows, self._letter_keys, strict=True):
            for char, key in zip(chars, keys, strict=True):
                key.set_text(char)
        self._shift.set_enabled(not self._symbols)  # symbols have no capitals
        if self._caps and not self._symbols:
            self._shift.classes(add="on")
        else:
            self._shift.classes(remove="on")
        self._draw_field()

    def _draw_field(self) -> None:
        if not self._secret:
            end = self.text[-VISIBLE_CHARS:]
            self._field.set_text(end if end == self.text else "…" + end)
        elif self._shown:
            self._field.set_text(self.text)
            self._show.props("icon=visibility_off")
        elif self._last_readable and self.text:
            self._field.set_text(HIDDEN * (len(self.text) - 1) + self.text[-1])
            self._show.props("icon=visibility")
        else:
            self._field.set_text(HIDDEN * len(self.text))
            self._show.props("icon=visibility")
