// Точка входа игрового экрана: соединение, состояние, черновик, отрисовка.

import { createBoard } from "./board.js";
import { createDraft } from "./draft.js";
import { checkGeometry } from "./placement.js";
import { createRack } from "./rack.js";
import { getState, setState, subscribe } from "./state.js";
import { askExchange, renderEndScreen, renderLog, renderUnknownWords } from "./ui.js";
import { createSocket } from "./ws.js";

const gameId = document.body.dataset.gameId;
const DRAFT_DEBOUNCE_MS = 120;

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
  preview: document.getElementById("preview"),
  commit: document.getElementById("commit"),
  reset: document.getElementById("reset"),
  exchange: document.getElementById("exchange"),
  pass: document.getElementById("pass"),
  blankDialog: document.getElementById("blank-dialog"),
  blankLetters: document.getElementById("blank-letters"),
  log: document.getElementById("log"),
  unknown: document.getElementById("unknown-words"),
};

let lastMoveNo = null;
let draftTimer = null;

const draft = createDraft({ onChange: onDraftChange });
const board = createBoard(document.getElementById("board"), { onCellClick });
const rack = createRack(document.getElementById("rack"), { onSelect: renderAll });

function showMessage(text, kind = "error") {
  elements.message.textContent = text ?? "";
  elements.message.className = `message ${kind}`;
  elements.message.hidden = !text;
  if (!text) elements.unknown.replaceChildren();
}

function showPreview(text, kind) {
  elements.preview.textContent = text ?? "";
  elements.preview.className = `preview ${kind ? `preview-${kind}` : ""}`;
}

function askBlankLetter(state) {
  return new Promise((resolve) => {
    elements.blankLetters.replaceChildren(
      ...state.alphabet.map((letter) => {
        const button = document.createElement("button");
        button.type = "submit";
        button.value = letter;
        button.className = "tile blank-letter";
        button.textContent = letter;
        return button;
      })
    );
    elements.blankDialog.addEventListener(
      "close",
      () => resolve(elements.blankDialog.returnValue || null),
      { once: true }
    );
    elements.blankDialog.showModal();
  });
}

async function onCellClick(row, col) {
  const state = getState();
  if (!state || state.status !== "active") return;

  if (draft.at(row, col)) {
    draft.remove(row, col);
    return;
  }
  if (state.board[row][col]) return;
  if (!state.your_turn) {
    showMessage("Сейчас ход соперника");
    return;
  }

  const tileId = rack.selected;
  if (tileId === null) {
    showMessage("Сначала выберите фишку на стойке");
    return;
  }
  const tile = state.rack.find((item) => item.id === tileId);
  if (!tile) return;

  showMessage(null);
  if (tile.letter === null) {
    const letter = await askBlankLetter(state);
    if (!letter) return;
    draft.put(row, col, { tileId, letter, isBlank: true });
  } else {
    draft.put(row, col, { tileId, letter: tile.letter });
  }
}

function onDraftChange(placements) {
  renderAll();
  clearTimeout(draftTimer);

  if (placements.length === 0) {
    showPreview(null);
    return;
  }

  const state = getState();
  const local = checkGeometry(state, placements);
  if (!local.valid && local.reason) {
    showPreview(local.reason, "bad");
    return;
  }

  showPreview("считаем…");
  draftTimer = setTimeout(
    () => socket.send({ type: "draft", placements: draft.payload() }),
    DRAFT_DEBOUNCE_MS
  );
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
    elements.turn.classList.remove("turn-mine");
    return;
  }
  elements.turn.textContent = state.your_turn ? "Ваш ход" : "Ход соперника";
  elements.turn.classList.toggle("turn-mine", state.your_turn);
}

function renderControls(state) {
  const active = state.status === "active" && state.your_turn;
  elements.commit.disabled = !active || draft.isEmpty();
  elements.reset.disabled = draft.isEmpty();
  elements.exchange.disabled = !active || state.bag < state.rack_size;
  elements.pass.disabled = !active;
}

function renderAll() {
  const state = getState();
  if (!state) return;
  board.render(state, draft);
  rack.render(state, draft);
  renderScores(state);
  renderTurn(state);
  renderControls(state);
  renderLog(elements.log, state);
  elements.bag.textContent = `В мешке фишек: ${state.bag}`;
  if (state.status === "finished") renderEndScreen(state);
}

subscribe((state) => {
  // ход состоялся — черновик больше не наш
  if (lastMoveNo !== null && state.move_no !== lastMoveNo) {
    draft.clear();
    showPreview(null);
    showMessage(null);
  }
  lastMoveNo = state.move_no;
  renderAll();
});

elements.commit.addEventListener("click", () => {
  if (draft.isEmpty()) return;
  socket.send({ type: "commit", placements: draft.payload() });
});

elements.reset.addEventListener("click", () => {
  draft.clear();
  showMessage(null);
});

elements.pass.addEventListener("click", () => {
  if (!confirm("Пропустить ход?")) return;
  draft.clear();
  socket.send({ type: "pass" });
});

elements.exchange.addEventListener("click", async () => {
  const state = getState();
  if (!state) return;
  draft.clear();
  const tileIds = await askExchange(state);
  if (tileIds && tileIds.length) socket.send({ type: "exchange", tile_ids: tileIds });
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
        players: state.players.map((p) => ({
          ...p,
          connected: online.get(p.id) ?? p.connected,
        })),
      });
    } else if (message.type === "preview") {
      if (message.valid) {
        const words = message.words.map(([word, points]) => `${word} — ${points}`);
        showPreview(`${words.join(", ")}. Итого ${message.total}`, "ok");
      } else {
        showPreview(message.error, "bad");
      }
    } else if (message.type === "error") {
      showMessage(message.message);
      // отказ из-за незнакомого слова — единственный, который игрок может
      // снять сам: словарь правится по ходу партии, без подтверждения
      renderUnknownWords(elements.unknown, message.unknown_words ?? [], (word) => {
        socket.send({ type: "allow_word", word });
        socket.send({ type: "commit", placements: draft.payload() });
        showMessage(null);
      });
    }
  },
});

window.addEventListener("beforeunload", () => socket.close());
