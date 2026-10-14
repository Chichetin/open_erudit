// Порядок фишек на стойке — забота только клиента: серверу всё равно, как
// игрок держит буквы. Храним список id; фишки, которых в нём нет (только что
// из мешка), встают в конец, ушедшие со стойки из списка выпадают.

export function arrange(order, tiles) {
  const position = new Map(order.map((id, index) => [id, index]));
  const known = tiles
    .filter((tile) => position.has(tile.id))
    .sort((a, b) => position.get(a.id) - position.get(b.id));
  const fresh = tiles.filter((tile) => !position.has(tile.id));
  return [...known, ...fresh];
}

// index — место среди остальных фишек, без перемещаемой
export function moveTo(order, tileId, index) {
  const rest = order.filter((id) => id !== tileId);
  rest.splice(Math.max(0, Math.min(index, rest.length)), 0, tileId);
  return rest;
}
