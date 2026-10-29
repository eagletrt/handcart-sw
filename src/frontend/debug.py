"""Debug page, only with simulated hardware: http://<frontend>/debug

The UI as on the display (800 x 480), and beside it switches that make the simulated shutdown loop, BMS and
charger misbehave. They write var/sim.json (shared/scenario.py); the simulator and the backend follow it
within a fraction of a second, and the UI reacts as it would on the handcart.
The browser plays what the buzzer plays (the backend sends each sound it starts), and a key for each sound
plays it on demand. Browsers stay silent until the page is clicked once.
"""

import json

from nicegui import Client, ui

from backend.hal.feedback import LOOP_CHANNELS
from backend.sounds.player import MELODIES
from frontend.backend import Backend
from shared import scenario
from shared.models import Sound

BUZZER_VOLUME = 0.05  # of the browser's square wave: a real square wave is loud

# Plays a Melody, [[frequency or null, seconds], ...], as a square wave; a new one cuts the one playing.
PLAY_MELODY_JS = """
<script>
let buzzer = null;
function playMelody(notes, volume) {
  const audio = (window.buzzerAudio = window.buzzerAudio || new AudioContext());
  audio.resume();
  if (buzzer) buzzer.stop();
  buzzer = audio.createOscillator();
  buzzer.type = "square";
  const gain = audio.createGain();
  gain.gain.value = 0;
  buzzer.connect(gain).connect(audio.destination);
  let t = audio.currentTime;
  for (const [frequency, seconds] of notes) {
    if (frequency === null) {
      gain.gain.setValueAtTime(0, t);
    } else {
      buzzer.frequency.setValueAtTime(frequency, t);
      gain.gain.setValueAtTime(volume, t);
    }
    t += seconds;
  }
  gain.gain.setValueAtTime(0, t);
  buzzer.start();
  buzzer.stop(t);
}
</script>
"""

CLOSED = "closed"
SWITCHES = {  # Scenario field: label
    "bms_unplugged": "BMS unplugged",
    "charger_unplugged": "Charger unplugged",
    "bms_fault": "BMS fault (overvoltage)",
    "charger_error": "Charger in ERROR",
    "high_cell": "A cell above the voltage limit",
    "hot_cell": "A probe above the temperature limit",
}


def build(backend: Backend) -> None:
    test = scenario.read()  # this page's copy; every change is written to the file at once

    def change(field: str, value: object) -> None:
        setattr(test, field, value)
        scenario.write(test)

    with ui.row().classes("items-start gap-6 p-4 no-wrap"):
        ui.element("iframe").props('src="/" width="800" height="480"').style("border: 1px solid #555")
        with ui.column().classes("gap-2"):
            ui.label("Simulated hardware").classes("text-h6")
            ui.label("Click the UI first to use the keys: arrows, Enter, Q and E for the knob.").classes(
                "text-caption"
            )
            options = {CLOSED: "closed"} | {point: f"open at {point}" for point in LOOP_CHANNELS.values()}
            loop = ui.select(
                options,
                value=test.shutdown_open_at or CLOSED,
                label="Shutdown loop",
                on_change=lambda e: change("shutdown_open_at", None if e.value == CLOSED else e.value),
            ).classes("w-64")
            switches = []
            for field, label in SWITCHES.items():
                switch = ui.switch(
                    label, value=getattr(test, field), on_change=lambda e, field=field: change(field, e.value)
                )
                switches.append(switch)

            def all_normal() -> None:
                loop.value = CLOSED  # each of these writes the file through its on_change
                for switch in switches:
                    switch.value = False

            ui.button("All normal", on_click=all_normal).props("outline")

            ui.label("Buzzer").classes("text-h6 mt-4")
            ui.label("What the buzzer plays is heard here too. Click the page once to let it sound.").classes(
                "text-caption"
            )
            ui.add_head_html(PLAY_MELODY_JS)
            client = ui.context.client
            with ui.grid(columns=2).classes("gap-2"):
                for sound in Sound:
                    label = sound.replace("_", " ").capitalize()
                    button = ui.button(label, on_click=lambda sound=sound: play(client, sound))
                    button.props("outline no-caps")
            client.on_disconnect(backend.on_sound(lambda sound: play(client, sound)))


def play(client: Client, sound: Sound) -> None:
    """Play the sound in this browser, as the buzzer would."""
    client.run_javascript(f"playMelody({json.dumps(MELODIES[sound])}, {BUZZER_VOLUME})")
