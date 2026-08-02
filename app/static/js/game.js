// Точка входа игрового экрана: соединение, состояние, отрисовка.

import { createBoard } from "./board.js";
import { createRack } from "./rack.js";
import { getState, setState, subscribe } from "./state.js";
import { createSocket } from "./ws.js";

const gameId = document.body.dataset.gameId;

// Токен приходит в hash-части ссылки — браузер не отправляет её на сервер,
// поэтому он не попадёт ни в логи uvicorn, ни в логи туннеля. Из адресной
// строки его убираем сразу: дальше он живёт в localStorage.
function readToken() {
  const key = `erudit:${gameId}`;
  const fromHash = location.hash.slice(1);
  if (fromHash) {
    localStorage.setItem(key, fromHash);
    history.replaceState(null, "", location.pathname);
    return fromHash;
  }
  return localStorage.getItem(key) ?? "";
}

const elements = {
  scores: document.getElementById("scores"),
  connection: document.getElementById("connection"),
  turn: document.getElementById("turn"),
  bag: document.getElementById("bag"),
  message: document.getElementById("message"),
};

const board = createBoard(document.getElementById("board"), {
  onCellClick: () => {},
});
const rack = createRack(document.getElementById("rack"), {
  onSelect: () => {},
});

function showMessage(text, kind = "error") {
  elements.message.textContent = text ?? "";
  elements.message.className = `message ${kind}`;
  elements.message.hidden = !text;
}

function renderScores(state) {
  elements.scores.replaceChildren(
    ...state.players.map((player) => {
      const item = document.createElement("span");
      item.className = "score";
      if (player.id === state.current) item.classList.add("score-active");
      if (!player.connected) item.classList.add("score-offline");
      item.textContent = `${player.name}${player.is_you ? " (вы)" : ""}: ${player.score}`;
      return item;
    })
  );
}

function renderTurn(state) {
  if (state.status === "finished") {
    elements.turn.textContent = "Партия окончена";
    return;
  }
  elements.turn.textContent = state.your_turn ? "Ваш ход" : "Ход соперника";
  elements.turn.classList.toggle("turn-mine", state.your_turn);
}

subscribe((state) => {
  board.render(state, null);
  rack.render(state, null);
  renderScores(state);
  renderTurn(state);
  elements.bag.textContent = `В мешке фишек: ${state.bag}`;
});

const socket = createSocket({
  gameId,
  token: readToken(),
  onStatus(status) {
    const labels = {
      online: "на связи",
      offline: "нет связи, переподключаемся…",
      unauthorized: "ссылка не подошла — откройте свою личную ссылку",
    };
    elements.connection.textContent = labels[status] ?? status;
    elements.connection.className = `connection connection-${status}`;
  },
  onMessage(message) {
    if (message.type === "state") {
      setState(message);
    } else if (message.type === "presence") {
      const state = getState();
      if (!state) return;
      const online = new Map(message.players.map((p) => [p.id, p.connected]));
      setState({
        ...state,
        players: state.players.map((p) => ({ ...p, connected: online.get(p.id) ?? p.connected })),
      });
    } else if (message.type === "error") {
      showMessage(message.message);
    }
  },
});

window.addEventListener("beforeunload", () => socket.close());
