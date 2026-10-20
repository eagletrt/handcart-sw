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

Then, in two terminals:

```bash
./handcart.py sim --speed 30   # charge 30 times faster than real life
./handcart.py backend
```

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

## Hardware notes

- **CAN**: the BMS and the rest of the car run at 1 Mbit/s. The charger runs at 250 kbit/s unless it is
  re-flashed. On a shared bus its `HYC_Error` frame (`0x1A0`) collides with `TsacMainboardShutdown`, so the
  charger also needs new IDs. `tests/test_dbc_contract.py` tracks this.
- **BMS watchdog**: the handcart sends `EcuFsm` every 0.2 s, standing in for the ECU.
- **Fonts**: Helvetica Neue is not on Raspberry Pi OS. Install `fonts-urw-base35` (Nimbus Sans) or
  `fonts-liberation` for a close match.

## Updating libcan

`libs/libcan` follows its `master` branch but stays on a fixed commit until you move it:

```bash
./handcart.py update-libcan
```

The DBC contract test fails if a message or signal the handcart uses was renamed or removed.
