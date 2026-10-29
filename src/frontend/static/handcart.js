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

// A finger on a chart of the Graphs window (graphs_window.py): a tap puts the line there, a drag scrolls
// the chart with the finger (or, not zoomed, takes the line along). The drag goes to the server at most
// every DRAG_PERIOD, as how far it moved in time: the server redraws the charts, once per finger move would
// be too many for the Pi.
const DRAG_START = 10; // px before a touch is a drag
const DRAG_PERIOD = 100; // ms
function chartFinger(id, event, emit) {
  const element = event.currentTarget;
  const chart = getElement(id).chart;
  const timeAt = (x) => chart.convertFromPixel({ gridIndex: 0 }, [x, 0])[0]; // ms since 1970
  if (event.type === 'pointerdown') {
    element.setPointerCapture(event.pointerId);
    element.finger = { x: event.offsetX, sentX: event.offsetX, dragging: false, sentAt: 0 };
    return;
  }
  const finger = element.finger;
  if (!finger) return;
  const lifted = event.type === 'pointerup' || event.type === 'pointercancel';
  if (lifted) element.finger = null;
  if (!finger.dragging) {
    if (event.type === 'pointerup') emit({ tap: timeAt(event.offsetX) });
    if (lifted || Math.abs(event.offsetX - finger.x) < DRAG_START) return;
    finger.dragging = true;
  }
  if (!lifted && performance.now() - finger.sentAt < DRAG_PERIOD) return;
  const moved = (timeAt(finger.sentX) - timeAt(event.offsetX)) / 1000; // s: the chart goes with the finger
  finger.sentX = event.offsetX;
  finger.sentAt = performance.now();
  if (moved) emit({ drag: moved, at: timeAt(event.offsetX) });
}

// A finger on the safe's dial (safe_window.py): the dial follows the finger around its center, and every
// DIAL_STEP degrees is one number, sent to the server as +1 to the right (clockwise) or -1 to the left.
const DIAL_STEP = 360 / 20; // safe.NUMBERS
function dialFinger(event, emit) {
  const element = event.currentTarget;
  const box = element.getBoundingClientRect();
  const dx = event.clientX - (box.left + box.width / 2);
  const dy = event.clientY - (box.top + box.height / 2);
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI; // grows clockwise: y goes down on the screen
  if (event.type === 'pointerdown') {
    element.setPointerCapture(event.pointerId);
    element.finger = { angle, turned: 0 };
    return;
  }
  const finger = element.finger;
  if (!finger) return;
  if (event.type !== 'pointermove') {
    element.finger = null;
    return;
  }
  let moved = angle - finger.angle;
  if (moved > 180) moved -= 360; // across the left side, where atan2 jumps from 180 to -180
  if (moved < -180) moved += 360;
  finger.angle = angle;
  finger.turned += moved;
  const steps = Math.trunc(finger.turned / DIAL_STEP);
  if (steps !== 0) {
    finger.turned -= steps * DIAL_STEP;
    emit(steps);
  }
}

// Play an element's CSS animation again from the start: the safe's door shaking at each wrong combination.
function replay(id, animationClass) {
  const element = document.getElementById('c' + id);
  if (!element) return;
  element.classList.remove(animationClass);
  void element.offsetWidth; // the browser must draw it once without the class, or the animation does not restart
  element.classList.add(animationClass);
}

// How fast the screen answers a touch, for the Debug window (debug_window.py), split in its three parts:
// the finger down until the browser makes it a click, the click until the first change the server sends,
// and that change until the browser has drawn it. A touch that changes nothing is not counted. The last
// TOUCHES touches are kept.
const TOUCHES = 20;
const ANSWER_WAIT = 1000; // ms: a change later than this after the click is not an answer to it
const touches = [];
let touch = null; // the touch being timed: {down, click}
document.addEventListener('pointerdown', () => { touch = { down: performance.now(), click: null }; }, true);
document.addEventListener('click', () => {
  if (touch && touch.click === null) touch.click = performance.now();
}, true);
function followServer() {
  if (!window.socket) return setTimeout(followServer, 500); // NiceGUI connects after the page loads
  window.socket.on('update', () => {
    if (!touch || touch.click === null) return;
    const timed = touch;
    touch = null;
    const answer = performance.now();
    if (answer - timed.click > ANSWER_WAIT) return;
    // two frames: the browser has drawn the change by the second one
    requestAnimationFrame(() => requestAnimationFrame(() => {
      touches.push({ click: timed.click - timed.down, server: answer - timed.click, draw: performance.now() - answer });
      if (touches.length > TOUCHES) touches.shift();
    }));
  });
}
followServer();
function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return Math.round(sorted[Math.floor(sorted.length / 2)]);
}
function touchLatency() {
  if (touches.length === 0) return null;
  return {
    count: touches.length,
    click: median(touches.map((t) => t.click)),
    server: median(touches.map((t) => t.server)),
    draw: median(touches.map((t) => t.draw)),
    total: median(touches.map((t) => t.click + t.server + t.draw)),
  };
}

// On the touch screen a button or a tab acts as soon as the finger is down, not when it lifts: a tap lasts
// some 100 ms, and the screen felt late by as much. The click the browser makes on the lift is then
// dropped wherever it lands: by then the press may have opened a window, and the lift would press what
// came up under the finger (Save, Shut down...). The mouse keeps the usual click.
let liftToDrop = false;
document.addEventListener('pointerdown', (event) => {
  liftToDrop = false;
  if (event.pointerType !== 'touch') return;
  const target = event.target.closest('.q-btn:not(.disabled):not([disabled]), .nt');
  if (!target) return;
  liftToDrop = true;
  target.click();
}, true);
document.addEventListener('click', (event) => {
  if (event.isTrusted && liftToDrop) {
    event.stopPropagation();
    event.preventDefault();
    liftToDrop = false;
  }
}, true);
