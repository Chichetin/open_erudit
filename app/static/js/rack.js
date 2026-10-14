// Стойка: свои фишки, их порядок и выбор одной из них.
// Фишки, уже положенные в черновик, показываются погашенными.

import { arrange, moveTo } from "./rackorder.js";

// Хранилище может быть недоступно (приватный режим) — тогда порядок просто
// живёт до перезагрузки страницы.
function loadOrder(key) {
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

function saveOrder(key, order) {
  try {
    localStorage.setItem(key, JSON.stringify(order));
  } catch {
    // не сохранили — не страшно
  }
}

export function createRack(root, { onSelect, storageKey }) {
  let selectedId = null;
  let order = loadOrder(storageKey);

  function select(tileId) {
    selectedId = selectedId === tileId ? null : tileId;
    onSelect(selectedId);
  }

  return {
    get selected() {
      return selectedId;
    },
    clearSelection() {
      selectedId = null;
    },
    move(tileId, index) {
      order = moveTo(order, tileId, index);
      saveOrder(storageKey, order);
    },
    render(state, draft) {
      const used = draft ? draft.usedTileIds() : new Set();
      if (selectedId !== null && used.has(selectedId)) selectedId = null;

      const tiles = arrange(order, state.rack);
      order = tiles.map((tile) => tile.id);
      saveOrder(storageKey, order);

      root.replaceChildren(
        ...tiles.map((tile) => {
          const element = document.createElement("button");
          element.type = "button";
          element.className = "tile rack-tile";
          element.dataset.tileId = tile.id;
          if (tile.letter === null) element.classList.add("tile-blank");
          if (used.has(tile.id)) element.classList.add("tile-used");
          if (tile.id === selectedId) element.classList.add("tile-selected");
          element.disabled = used.has(tile.id);
          element.append(
            Object.assign(document.createElement("span"), {
              className: "tile-letter",
              textContent: tile.letter ?? "•",
            }),
            Object.assign(document.createElement("sub"), {
              className: "tile-value",
              textContent: tile.value ? String(tile.value) : "",
            })
          );
          element.addEventListener("click", () => select(tile.id));
          return element;
        })
      );
    },
  };
}
