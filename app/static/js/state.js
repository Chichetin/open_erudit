// Последний снапшот от сервера и подписка на его обновления.
// Сервер шлёт состояние целиком, поэтому склеивать здесь нечего.

const listeners = new Set();
let current = null;

export function setState(state) {
  current = state;
  for (const listener of listeners) listener(current);
}

export function getState() {
  return current;
}

export function subscribe(listener) {
  listeners.add(listener);
  if (current) listener(current);
  return () => listeners.delete(listener);
}
