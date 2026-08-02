// Перетаскивание фишек — отдельный слой ввода поверх того же черновика.
//
// На Pointer Events, чтобы мышь и касание обрабатывались одним кодом.
// Тап никуда не девается и остаётся рабочим: это запасной путь, если
// перетаскивание где-то ведёт себя плохо.

const DRAG_THRESHOLD_PX = 4;

export function enableDragAndDrop({ boardRoot, rackRoot, onDrop, onPickUp }) {
  let dragging = null;

  function ghostFor(element) {
    const ghost = element.cloneNode(true);
    ghost.classList.add("tile-ghost");
    ghost.style.width = `${element.offsetWidth}px`;
    ghost.style.height = `${element.offsetHeight}px`;
    document.body.append(ghost);
    return ghost;
  }

  function moveGhost(event) {
    dragging.ghost.style.left = `${event.clientX - dragging.offsetX}px`;
    dragging.ghost.style.top = `${event.clientY - dragging.offsetY}px`;
  }

  function cellUnder(event) {
    dragging.ghost.style.visibility = "hidden";
    const target = document.elementFromPoint(event.clientX, event.clientY);
    dragging.ghost.style.visibility = "";
    return target?.closest(".cell") ?? null;
  }

  function start(event, source) {
    const element = source.element;
    const box = element.getBoundingClientRect();
    dragging = {
      ...source,
      ghost: ghostFor(element),
      offsetX: event.clientX - box.left,
      offsetY: event.clientY - box.top,
      moved: false,
      startX: event.clientX,
      startY: event.clientY,
    };
    moveGhost(event);
  }

  function finish(event) {
    if (!dragging) return;
    const cell = dragging.moved ? cellUnder(event) : null;
    dragging.ghost.remove();
    const source = dragging;
    dragging = null;

    if (!source.moved) return; // это был обычный тап — им занимается rack.js
    if (!cell) {
      source.onCancel?.();
      return;
    }
    onDrop({
      tileId: source.tileId,
      from: source.from,
      row: Number(cell.dataset.row),
      col: Number(cell.dataset.col),
    });
  }

  function attach(root, resolveSource) {
    root.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      const source = resolveSource(event);
      if (!source) return;
      start(event, source);
    });
  }

  attach(rackRoot, (event) => {
    const element = event.target.closest(".rack-tile");
    if (!element || element.disabled) return null;
    return { element, tileId: Number(element.dataset.tileId), from: "rack" };
  });

  attach(boardRoot, (event) => {
    const cell = event.target.closest(".cell");
    const tile = event.target.closest(".tile-draft");
    if (!cell || !tile) return null;
    const row = Number(cell.dataset.row);
    const col = Number(cell.dataset.col);
    const drafted = onPickUp(row, col);
    if (!drafted) return null;
    return { element: tile, tileId: drafted.tileId, from: { row, col } };
  });

  window.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    if (!dragging.moved) {
      const far =
        Math.abs(event.clientX - dragging.startX) > DRAG_THRESHOLD_PX ||
        Math.abs(event.clientY - dragging.startY) > DRAG_THRESHOLD_PX;
      if (!far) return;
      dragging.moved = true;
    }
    event.preventDefault();
    moveGhost(event);
  });

  window.addEventListener("pointerup", finish);
  window.addEventListener("pointercancel", finish);
}
