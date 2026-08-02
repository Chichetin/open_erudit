// Соединение с сервером: hello при каждом открытии, переподключение с
// нарастающей паузой. Отдельной логики восстановления не нужно — после hello
// сервер присылает полный снапшот, и клиент продолжает с того же места.

const FIRST_DELAY = 500;
const MAX_DELAY = 10000;
const UNAUTHORIZED = 4401;

export function createSocket({ gameId, token, onMessage, onStatus }) {
  let socket = null;
  let delay = FIRST_DELAY;
  let stopped = false;

  function open() {
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${scheme}//${location.host}/g/${gameId}/ws`);

    socket.addEventListener("open", () => {
      delay = FIRST_DELAY;
      onStatus("online");
      socket.send(JSON.stringify({ type: "hello", token }));
    });

    socket.addEventListener("message", (event) => {
      onMessage(JSON.parse(event.data));
    });

    socket.addEventListener("close", (event) => {
      if (stopped) return;
      if (event.code === UNAUTHORIZED) {
        onStatus("unauthorized");
        return;
      }
      onStatus("offline");
      setTimeout(open, delay);
      delay = Math.min(delay * 2, MAX_DELAY);
    });
  }

  open();

  return {
    send(message) {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
      }
    },
    close() {
      stopped = true;
      socket?.close();
    },
  };
}
