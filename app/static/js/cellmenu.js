// Меню над клеткой: фишки со стойки, ещё не лежащие в черновике. Клик по
// пустой клетке открывает его, клик по фишке ставит её в эту клетку — не
// нужно водить мышью к стойке и обратно.

const GAP_PX = 4;
const EDGE_PX = 8;

export function createCellMenu({ onPick }) {
  const menu = document.createElement("div");
  menu.className = "cell-menu";
  menu.hidden = true;
  document.body.append(menu);

  let target = null; // {row, col}
  let targetCell = null;

  function tileButton(tile) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tile menu-tile";
    if (tile.letter === null) button.classList.add("tile-blank");
    button.append(
      Object.assign(document.createElement("span"), {
        className: "tile-letter",
        textContent: tile.letter ?? "•",
      }),
      Object.assign(document.createElement("sub"), {
        className: "tile-value",
        textContent: tile.value ? String(tile.value) : "",
      })
    );
    button.addEventListener("click", () => {
      const { row, col } = target;
      close();
      onPick(row, col, tile.id);
    });
    return button;
  }

  // Над клеткой, а у верхнего края доски — под ней; по горизонтали по
  // центру клетки, но не за краем окна.
  function place(cell) {
    const box = cell.getBoundingClientRect();
    const width = menu.offsetWidth;
    const height = menu.offsetHeight;

    let top = box.top - height - GAP_PX;
    if (top < EDGE_PX) top = box.bottom + GAP_PX;

    const maxLeft = window.innerWidth - width - EDGE_PX;
    const left = Math.max(EDGE_PX, Math.min(box.left + box.width / 2 - width / 2, maxLeft));

    menu.style.top = `${top + window.scrollY}px`;
    menu.style.left = `${left + window.scrollX}px`;
  }

  function open(cell, row, col, tiles) {
    close();
    target = { row, col };
    targetCell = cell;
    targetCell.classList.add("cell-target");
    menu.replaceChildren(...tiles.map(tileButton));
    menu.hidden = false;
    place(cell);
  }

  function close() {
    menu.hidden = true;
    target = null;
    targetCell?.classList.remove("cell-target");
    targetCell = null;
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  // клики по клеткам разбирает сама доска: там меню переоткрывается
  document.addEventListener("click", (event) => {
    if (menu.contains(event.target) || event.target.closest(".cell")) return;
    close();
  });
  window.addEventListener("resize", close);

  return {
    open,
    close,
    isOpenAt(row, col) {
      return target !== null && target.row === row && target.col === col;
    },
  };
}
