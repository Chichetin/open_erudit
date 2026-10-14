// Точка входа игрового экрана: соединение, состояние, черновик, отрисовка.

import { createBoard } from "./board.js";
import { createCellMenu } from "./cellmenu.js";
import { createDraft } from "./draft.js";
import { enableDragAndDrop } from "./dragdrop.js";
import { createTurnNotifier } from "./notify.js";
import { checkGeometry } from "./placement.js";
import { createRack } from "./rack.js";
import { getState, setState, subscribe } from "./state.js";
import {
  askExchange,
  renderEndScreen,
  renderLog,
  renderUnknownWords,
  renderUnseen,
  rematchUrl,
} from "./ui.js";
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
  lettersToggle: document.getElementById("letters-toggle"),
  lettersPanel: document.getElementById("letters-panel"),
  lettersClose: document.getElementById("letters-close"),
  lettersBody: document.getElementById("letters-body"),
};

let lastMoveNo = null;
let draftTimer = null;
let rematchRequested = false;
let scoreHint = null;
let opponentDraft = []; // очки за текущий черновик, пока сервер считает — null

const draft = createDraft({ onChange: onDraftChange });
const board = createBoard(document.getElementById("board"), { onCellClick });
const rack = createRack(document.getElementById("rack"), {
  onSelect: renderAll,
  storageKey: `erudit:${gameId}:rack`,
});
const cellMenu = createCellMenu({ onPick: putFromRack });
const notifier = createTurnNotifier(document.getElementById("notify"));

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
    // returnValue переживает закрытие диалога: без сброса Esc вернул бы
    // букву, выбранную в прошлый раз
    elements.blankDialog.returnValue = "";
    elements.blankDialog.addEventListener(
      "close",
      () => resolve(elements.blankDialog.returnValue || null),
      { once: true }
    );
    elements.blankDialog.showModal();
  });
}

async function putFromRack(row, col, tileId) {
  const state = getState();
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

function canPlaceAt(state, row, col) {
  if (!state || state.status !== "active") return false;
  if (state.board[row][col]) return false;
  if (!state.your_turn) {
    showMessage("Сейчас ход соперника");
    return false;
  }
  return true;
}

async function onCellClick(row, col) {
  const state = getState();
  if (!state || state.status !== "active") return;

  const menuWasHere = cellMenu.isOpenAt(row, col);
  cellMenu.close();

  if (draft.at(row, col)) {
    draft.remove(row, col);
    return;
  }
  if (!canPlaceAt(state, row, col)) return;

  // фишка уже выбрана на стойке — ставим её, как раньше, без меню
  const tileId = rack.selected;
  if (tileId !== null) {
    await putFromRack(row, col, tileId);
    return;
  }
  if (menuWasHere) return; // повторный клик по той же клетке закрывает меню

  const used = draft.usedTileIds();
  const free = state.rack.filter((tile) => !used.has(tile.id));
  if (free.length === 0) {
    showMessage("Все фишки уже на доске");
    return;
  }
  showMessage(null);
  cellMenu.open(board.cellElement(row, col), row, col, free);
}

// Перетаскивание пишет в тот же черновик, что и тап.
async function onDrop({ tileId, from, row, col }) {
  cellMenu.close();
  const state = getState();
  if (!canPlaceAt(state, row, col)) return;

  if (from === "rack") {
    await putFromRack(row, col, tileId);
    return;
  }
  // фишку двигают по доске: у пустышки уже выбрана буква, не спрашиваем снова
  const existing = draft.at(from.row, from.col);
  if (existing) {
    draft.put(row, col, {
      tileId: existing.tileId,
      letter: existing.letter,
      isBlank: existing.isBlank,
    });
  }
}

// Фишку перетащили на стойку: со стойки — меняем порядок, с доски —
// возвращаем из черновика на выбранное место.
function onRackDrop({ tileId, from, index }) {
  cellMenu.close();
  rack.move(tileId, index);
  if (from === "rack") {
    renderAll();
  } else {
    draft.remove(from.row, from.col);
  }
}

function shareDraft() {
  if (getState()?.show_drafts) socket.send({ type: "share_draft", placements: draft.payload() });
}

function onDraftChange(placements) {
  scoreHint = null;
  renderAll();
  clearTimeout(draftTimer);

  if (placements.length === 0) {
    showPreview(null);
    shareDraft();
    return;
  }

  const state = getState();
  const local = checkGeometry(state, placements);
  if (!local.valid && local.reason) {
    showPreview(local.reason, "bad");
    return;
  }

  showPreview("считаем…");
  draftTimer = setTimeout(() => {
    socket.send({ type: "draft", placements: draft.payload() });
    shareDraft();
  }, DRAFT_DEBOUNCE_MS);
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
  board.render(state, draft, scoreHint, opponentDraft);
  rack.render(state, draft);
  renderScores(state);
  renderTurn(state);
  renderControls(state);
  renderLog(elements.log, state);
  elements.bag.textContent = `В мешке фишек: ${state.bag}`;
  renderUnseen(elements.lettersBody, state);
  if (state.status === "finished") {
    renderEndScreen(state, {
      rematchRequested,
      onRematch() {
        rematchRequested = true;
        socket.send({ type: "rematch" });
        renderAll();
      },
    });
  }
}

subscribe((state) => {
  // ход состоялся — черновик больше не наш
  if (lastMoveNo !== null && state.move_no !== lastMoveNo) {
    opponentDraft = [];
    cellMenu.close();
    draft.clear();
    showPreview(null);
    showMessage(null);
  }
  lastMoveNo = state.move_no;
  // реванш попросили отсюда — сразу уводим в новую партию
  if (rematchRequested && state.rematch) {
    location.assign(rematchUrl(state.rematch));
    return;
  }
  notifier.update(state);
  renderAll();
});

elements.commit.addEventListener("click", () => {
  if (draft.isEmpty()) return;
  socket.send({ type: "commit", placements: draft.payload() });
});

elements.reset.addEventListener("click", () => {
  cellMenu.close();
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

function setLettersOpen(open) {
  elements.lettersPanel.classList.toggle("letters-open", open);
  elements.lettersPanel.inert = !open;
  elements.lettersToggle.setAttribute("aria-expanded", String(open));
}

elements.lettersToggle.addEventListener("click", () => {
  setLettersOpen(!elements.lettersPanel.classList.contains("letters-open"));
});
elements.lettersClose.addEventListener("click", () => setLettersOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setLettersOpen(false);
});
document.addEventListener("click", (event) => {
  if (elements.lettersPanel.contains(event.target)) return;
  if (elements.lettersToggle.contains(event.target)) return;
  setLettersOpen(false);
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
    } else if (message.type === "opponent_draft") {
      opponentDraft = message.placements;
      renderAll();
    } else if (message.type === "preview") {
      if (message.valid) {
        const words = message.words.map(([word, points]) => `${word} — ${points}`);
        showPreview(`${words.join(", ")}. Итого ${message.total}`, "ok");
        scoreHint = message.total;
        renderAll();
      } else {
        showPreview(message.error, "bad");
      }
    } else if (message.type === "error") {
      rematchRequested = false;
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

enableDragAndDrop({
  boardRoot: document.getElementById("board"),
  rackRoot: document.getElementById("rack"),
  onDrop,
  onRackDrop,
  onPickUp: (row, col) => draft.at(row, col),
});

window.addEventListener("beforeunload", () => socket.close());
