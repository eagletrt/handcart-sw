<p align="center"><img src="assets/eagle.png" width="96" alt="E-Agle TRT"></p>

# Handcart

Software of the E-Agle TRT handcart, the cart that carries and charges the HV accumulator.
A Raspberry Pi drives the charge over CAN, talking to the BMS (TSAC) and to the alpitronic
LittleSIC charger, and shows it on a small touch display.

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/) and git with access to the eagletrt repos.

```bash
git clone --recurse-submodules git@github.com:eagletrt/handcart-sw.git
cd handcart-sw
./handcart.py setup     # submodules + dependencies
./handcart.py test
```

Run `./handcart.py` with no arguments for the list of commands.

| Command | What it does |
|---|---|
| `setup` | Fetch the submodules and install the dependencies |
| `backend` / `frontend` / `sim` | Run one part |
| `test` / `lint` / `format` / `typecheck` | Checks |
| `vcan-up` | Create `vcan0` for the simulator |
| `status` | Show what the running backend sees |
| `command <NAME>` | Send a command to the state machine, e.g. `command STOP` |
| `update` | Update to the latest commit of the branch in `config.toml`, then restart (goes back if it fails) |
| `install-services` | Set up the Pi to boot straight into the handcart UI |
| `update-libcan` | Move libcan to its latest commit and run the tests |

## On your computer

The simulator plays the BMS and the charger, so the backend runs without the handcart.
Linux `vcan` does not exist on macOS or Windows, so off the Pi CAN goes over UDP between processes.
Create `config.local.toml` (not in git), which overrides `config.toml` on this machine only:

```toml
[can]
interface = "udp_multicast"
```

Then, in three terminals:

```bash
./handcart.py sim --speed 30   # charge 30 times faster than real life
./handcart.py backend
./handcart.py frontend         # then open http://127.0.0.1:8080, best at 800 x 480 like the display
```

On the computer the keyboard and the mouse stand in for the handcart's controls:

| Handcart | Computer |
|---|---|
| left / right buttons | ← / → |
| up / down buttons | ↑ / ↓ |
| turning the encoder | Q / E, or the mouse wheel |
| clicking the encoder | Enter or Space |

What they do (the rules are in `src/frontend/controls.py`):

- ← → change screen; inside a window or the cell map they move instead.
- ↑ ↓ move a yellow frame over the screen's buttons; a click presses the framed one. After a pause the
  first click only shows the frame: on STOP while something runs, else on the main action.
- Turning the encoder on Charge drafts a new target voltage on the rail: a click sets it, any arrow
  (or a pause) cancels it; not while charging, when the target changes only from the settings window.
  In the settings window turning changes the framed value (1 V or 0.1 A a step, five times that when
  turned fast), and a click saves.
- On Cells, a click, a touch on a cell, or pressing Volts or Temps with the controls puts a cursor on the
  map: the arrows and the encoder move it and the reading shows under the map; a click takes it away.

## Layout

```
handcart.py        launcher, standard library only
config.toml        limits, timings, pins, interfaces
libs/              submodules: libcan (primary DBC), charger/littlesic (charger DBC)
src/
  backend/         owns CAN, GPIO, the charge state machine and safety; exposes the API
    hal/           GPIO, ADC, buzzer, buttons, with fakes for your computer
    canbus/        buses, DBC encoding, periodic frames
    devices/       BMS and charger
    core/          charge state machine, free of hardware
    auth/          operators, PINs, audit log
    api/           REST and WebSocket
  frontend/        touch UI (NiceGUI), talks only to the API
  shared/          models used by both
  sim/             simulated BMS and charger on vcan
system/            what gets installed on the Pi (see below)
tests/
```

The backend runs on its own: if the frontend crashes, the charge and the protections keep running.

## On the Pi

The Pi boots straight into the handcart UI: the eagle splash from power-on, then the touch interface.
No desktop, no boot text, no login prompt. Use Raspberry Pi OS Lite.

`system/` holds what the Pi needs besides the code. Each file says in its header where it goes.

| File | What it is |
|---|---|
| `services/handcart-backend.service` | Starts the backend at boot and restarts it if it stops |
| `services/handcart-frontend.service` | Starts the frontend after the backend |
| `services/handcart-display.service` | Shows the frontend full screen (Chromium kiosk in `cage`) once it answers |
| `can/can0.network` | Brings `can0` up at 1 Mbit/s at boot |
| `splash/` | Boot splash: the eagle on black, from power-on until the UI appears |
| `raspberry/boot-config.txt` | Lines for `/boot/firmware/config.txt`: SPI, CAN controller, UART, no rainbow square |
| `raspberry/cmdline.txt` | Kernel parameters for a silent boot |

Setup, once:

```bash
sudo apt install cage chromium-browser plymouth curl fonts-urw-base35
./handcart.py setup
./handcart.py install-services
```

Then by hand, because a mistake there stops the Pi from booting:

1. Append `system/raspberry/boot-config.txt` to `/boot/firmware/config.txt`.
2. Add the parameters in `system/raspberry/cmdline.txt` to the end of the single line in
   `/boot/firmware/cmdline.txt`, and change `console=tty1` to `console=tty3` in that line.
3. Reboot.

To reach the Pi for maintenance, use SSH: the display only ever shows the UI.
The backend only accepts connections from the Pi itself, so from an SSH session:

```bash
./handcart.py status
./handcart.py command STOP
```

## Hardware notes

- **CAN**: the BMS and the rest of the car run at 1 Mbit/s. The charger runs at 250 kbit/s unless it is
  re-flashed. On a shared bus libcan reserves every charger ID with a dummy `ChargerNNN` message, so no car
  message can take one: `tests/test_dbc_contract.py` checks it.
- **BMS requests**: `BmsSet` and `RaspberryTsacBalancingSet` are sent only when they change (5 frames each),
  and no `EcuFsm` heartbeat is sent: this is what the charge script that worked on the TSAC did.
- **Fonts**: Helvetica Neue is not on Raspberry Pi OS. Install `fonts-urw-base35` (Nimbus Sans) or
  `fonts-liberation` for a close match.

## Updating libcan

`libs/libcan` follows its `master` branch but stays on a fixed commit until you move it:

```bash
./handcart.py update-libcan
```

The DBC contract test fails if a message or signal the handcart uses was renamed or removed.
