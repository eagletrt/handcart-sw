// Browser side of the handcart UI: fit the screen to the display, and the physical controls.

// The layout is drawn 480 px tall and as wide as the display's aspect ratio, then zoomed to fill it:
// text and buttons keep the same physical size at any resolution.
function fitScreen() {
  const screen = document.querySelector('.screen');
  if (!screen) return;
  screen.style.width = Math.round((480 * innerWidth) / innerHeight) + 'px';
  screen.style.zoom = innerHeight / 480;
}
addEventListener('resize', fitScreen);

// Arrow buttons and encoder move the focus between the buttons on screen; the encoder click presses one.
// Inside an open window (settings, info) only its buttons take part.
function focusableButtons() {
  const visible = (el) => el.offsetParent !== null;
  const openModal = [...document.querySelectorAll('.screen .modal')].find(visible);
  const scope = openModal || document.querySelector('.screen');
  return [...scope.querySelectorAll('button:not([disabled]), .nt')].filter(visible);
}

function moveFocus(step) {
  const buttons = focusableButtons();
  if (!buttons.length) return;
  const current = buttons.indexOf(document.activeElement);
  const next = current === -1 ? 0 : (current + step + buttons.length) % buttons.length;
  buttons[next].setAttribute('tabindex', '0');
  buttons[next].focus();
}

function pressFocused() {
  if (focusableButtons().includes(document.activeElement)) document.activeElement.click();
}

// Under the cell map, the reading of one cell: tapped (touch has no hover), or the faulty one. null clears it.
function showCellDetail(text, fault = false) {
  const detail = document.getElementById('cell-detail');
  if (!detail) return;
  detail.textContent = text ?? 'Tap a cell to read it';
  detail.classList.toggle('hint', text == null);
  detail.style.color = fault ? 'var(--red)' : '';
}

document.addEventListener('click', (event) => {
  const cell = event.target.closest('.cmap .c');
  if (cell) showCellDetail(cell.dataset.l, cell.classList.contains('flt'));
});
