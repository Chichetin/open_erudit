// Стойка: свои фишки и выбор одной из них.
// Фишки, уже положенные в черновик, показываются погашенными.

export function createRack(root, { onSelect }) {
  let selectedId = null;

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
    render(state, draft) {
      const used = draft ? draft.usedTileIds() : new Set();
      if (selectedId !== null && used.has(selectedId)) selectedId = null;

      root.replaceChildren(
        ...state.rack.map((tile) => {
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
