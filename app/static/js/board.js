// Доска 15×15 на CSS Grid. Сетка строится один раз, дальше только
// обновляется содержимое клеток — так проще пережить перерисовку черновика.

const BONUS_CLASS = {
  T: "bonus-tw",
  D: "bonus-dw",
  t: "bonus-tl",
  d: "bonus-dl",
  "*": "bonus-center",
  ".": "",
};

const BONUS_LABEL = {
  T: "3×сл",
  D: "2×сл",
  t: "3×бк",
  d: "2×бк",
  "*": "★",
};

export function createBoard(root, { onCellClick }) {
  let cells = [];
  let size = 0;

  function build(state) {
    size = state.bonuses.length;
    root.style.setProperty("--board-size", size);
    cells = [];
    const fragment = document.createDocumentFragment();
    for (let row = 0; row < size; row += 1) {
      for (let col = 0; col < size; col += 1) {
        const cell = document.createElement("div");
        cell.className = "cell";
        cell.dataset.row = row;
        cell.dataset.col = col;
        const bonus = state.bonuses[row][col];
        if (BONUS_CLASS[bonus]) cell.classList.add(BONUS_CLASS[bonus]);
        cell.addEventListener("click", () => onCellClick(row, col));
        cells.push(cell);
        fragment.append(cell);
      }
    }
    root.replaceChildren(fragment);
  }

  function tileElement(letter, { isBlank, isNew, isLast }) {
    const tile = document.createElement("div");
    tile.className = "tile";
    if (isBlank) tile.classList.add("tile-blank");
    if (isNew) tile.classList.add("tile-draft");
    if (isLast) tile.classList.add("tile-last");
    tile.textContent = letter;
    return tile;
  }

  return {
    render(state, draft) {
      if (!cells.length) build(state);
      for (let row = 0; row < size; row += 1) {
        for (let col = 0; col < size; col += 1) {
          const cell = cells[row * size + col];
          const placed = state.board[row][col];
          const drafted = draft?.at(row, col);
          cell.classList.toggle("cell-drafted", Boolean(drafted));

          if (placed) {
            cell.replaceChildren(
              tileElement(placed.letter, {
                isBlank: placed.is_blank,
                isLast: placed.is_last,
              })
            );
          } else if (drafted) {
            cell.replaceChildren(
              tileElement(drafted.letter, { isBlank: drafted.isBlank, isNew: true })
            );
          } else {
            const bonus = state.bonuses[row][col];
            cell.replaceChildren(
              BONUS_LABEL[bonus]
                ? Object.assign(document.createElement("span"), {
                    className: "bonus-label",
                    textContent: BONUS_LABEL[bonus],
                  })
                : ""
            );
          }
        }
      }
    },
  };
}
