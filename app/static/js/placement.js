// Быстрая проверка геометрии — только ради подсветки в интерфейсе.
//
// ЭТО КОПИЯ ПРАВИЛ ИЗ erudit/rules.py, и дублирование здесь осознанное:
// нужен мгновенный отклик, не дожидаясь ответа сервера. Источник истины —
// именно `erudit/rules.py`. Ход, принятый этим кодом, но отклонённый
// сервером, — отклонённый ход. При расхождении правится этот файл.

export function checkGeometry(state, placements) {
  if (placements.length === 0) return { valid: false, reason: null };

  const size = state.bonuses.length;
  const cells = placements.map(({ row, col }) => [row, col]);

  for (const [row, col] of cells) {
    if (row < 0 || col < 0 || row >= size || col >= size) {
      return { valid: false, reason: "Фишка вне доски" };
    }
    if (state.board[row][col]) return { valid: false, reason: "Клетка уже занята" };
  }

  const keys = new Set(cells.map(([r, c]) => `${r},${c}`));
  if (keys.size !== cells.length) {
    return { valid: false, reason: "Две фишки в одной клетке" };
  }

  const rows = new Set(cells.map(([r]) => r));
  const cols = new Set(cells.map(([, c]) => c));
  const horizontal = rows.size === 1;
  if (!horizontal && cols.size !== 1) {
    return { valid: false, reason: "Фишки должны лежать в одной строке или в одном столбце" };
  }

  const filled = (row, col) =>
    Boolean(state.board[row]?.[col]) || keys.has(`${row},${col}`);

  const line = horizontal ? cells.map(([, c]) => c) : cells.map(([r]) => r);
  const fixed = horizontal ? cells[0][0] : cells[0][1];
  for (let i = Math.min(...line); i <= Math.max(...line); i += 1) {
    const [row, col] = horizontal ? [fixed, i] : [i, fixed];
    if (!filled(row, col)) return { valid: false, reason: "В слове есть разрыв" };
  }

  const boardEmpty = state.board.every((row) => row.every((cell) => !cell));
  if (boardEmpty) {
    const [centerRow, centerCol] = state.center;
    if (!keys.has(`${centerRow},${centerCol}`)) {
      return { valid: false, reason: "Первый ход должен накрыть центральную клетку" };
    }
    return { valid: true, reason: null };
  }

  const touches = cells.some(([row, col]) =>
    [
      [row - 1, col],
      [row + 1, col],
      [row, col - 1],
      [row, col + 1],
    ].some(([r, c]) => state.board[r]?.[c])
  );
  if (!touches) return { valid: false, reason: "Слово должно касаться уже выложенных фишек" };

  return { valid: true, reason: null };
}
