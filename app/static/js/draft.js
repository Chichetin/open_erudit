// Черновик хода — единственный источник правды интерфейса о незавершённом
// ходе. Тап и перетаскивание пишут сюда оба; отправляется на сервер тоже
// только то, что здесь лежит.

export function createDraft({ onChange }) {
  const byCell = new Map(); // "row,col" -> {row, col, tileId, letter, isBlank}

  const key = (row, col) => `${row},${col}`;

  function changed() {
    onChange(list());
  }

  function list() {
    return [...byCell.values()];
  }

  return {
    at(row, col) {
      return byCell.get(key(row, col)) ?? null;
    },
    put(row, col, { tileId, letter, isBlank = false }) {
      // одна фишка не может лежать в двух клетках сразу
      for (const [cellKey, item] of byCell) {
        if (item.tileId === tileId) byCell.delete(cellKey);
      }
      byCell.set(key(row, col), { row, col, tileId, letter, isBlank });
      changed();
    },
    remove(row, col) {
      if (byCell.delete(key(row, col))) changed();
    },
    clear() {
      if (byCell.size === 0) return;
      byCell.clear();
      changed();
    },
    isEmpty() {
      return byCell.size === 0;
    },
    usedTileIds() {
      return new Set(list().map((item) => item.tileId));
    },
    list,
    payload() {
      return list().map(({ row, col, tileId, letter }) => ({
        row,
        col,
        tile_id: tileId,
        letter,
      }));
    },
  };
}
