// Browser side of the handcart UI: fit the screen to the display, and the physical controls.

// The layout is drawn 480 px tall and as wide as the display's aspect ratio, then zoomed to fill it:
// text and buttons keep the same physical size at any resolution.
function fitScreen() {
  const screen = document.querySelector('.screen');
  if (!screen) return;
  screen.style.width = Math.round((480 * innerWidth) / innerHeight) + 'px';
  screen.style.zoom = innerHeight / 480;
  document.getElementById('boot')?.remove(); // the UI is drawn: the eagle of the boot splash can go
}
addEventListener('resize', fitScreen);

// The display's kiosk browser opens the page with ?kiosk=true: it is a touch screen, so no mouse pointer.
if (new URLSearchParams(location.search).has('kiosk')) document.documentElement.classList.add('kiosk');

// On a computer the keyboard and the mouse wheel stand in for the handcart's controls: they become the
// same events (shared.models.InputEvent), and the page handles them as if they came from the handcart.
const KEYS = {
  ArrowLeft: 'LEFT', ArrowRight: 'RIGHT', ArrowUp: 'UP', ArrowDown: 'DOWN',
  Enter: 'PRESS', ' ': 'PRESS', q: 'TURN_CCW', e: 'TURN_CW',
};

// While a screen keyboard is open (the Wi-Fi password, the terminal) a USB keyboard types into it instead:
// characters, Backspace, Enter to confirm and Escape to go back.
const TYPING_KEYS = new Set(['Backspace', 'Enter', 'Escape']);
function typing() {
  return [...document.querySelectorAll('.kb')].some((kb) => kb.offsetParent !== null);
}

// In the capture phase, before the buttons see the key: a focused Quasar button would take Enter and
// Space for itself and press itself again on key up.
document.addEventListener('keydown', (event) => {
  const typed = event.key.length === 1 || TYPING_KEYS.has(event.key);
  if (typed && !event.ctrlKey && !event.metaKey && !event.altKey && typing()) {
    event.preventDefault();
    event.stopPropagation();
    emitEvent('handcart_type', event.key);
    return;
  }
  const control = KEYS[event.key];
  if (control === undefined) return;
  event.preventDefault(); // no scrolling, no native press
  event.stopPropagation();
  if (!event.repeat) emitEvent('handcart_control', control);
}, { capture: true });
document.addEventListener('keyup', (event) => {
  if (KEYS[event.key] !== undefined) event.stopPropagation();
}, { capture: true });

const WHEEL_STEP = 100; // about one notch of a mouse wheel; a trackpad sends many small deltas
let wheel = 0;
document.addEventListener('wheel', (event) => {
  wheel += event.deltaY;
  while (Math.abs(wheel) >= WHEEL_STEP) {
    const direction = Math.sign(wheel);
    wheel -= direction * WHEEL_STEP;
    emitEvent('handcart_control', direction > 0 ? 'TURN_CW' : 'TURN_CCW');
  }
}, { passive: true });

// A touch: on a square of the cell map it selects that square, anywhere else the frame of the controls goes.
// On pointerdown, not on click: the map is redrawn several times a second, and a click needs the same
// element under the finger when it goes down and when it lifts.
document.addEventListener('pointerdown', (event) => {
  if (!event.isTrusted) return;
  const square = event.target.closest('.cmap .c');
  if (square) emitEvent('handcart_cell', Number(square.dataset.i));
  else emitEvent('handcart_touch');
});
