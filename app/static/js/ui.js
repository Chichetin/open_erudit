// Части интерфейса, не связанные с доской: журнал, диалог обмена,
// предложение добавить слово в словарь, оставшиеся буквы, экран конца партии.

// Значение слова — из Викисловаря через сервер. Окно одно на страницу.
async function showMeaning(word) {
  let dialog = document.getElementById("meaning-dialog");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "meaning-dialog";
    dialog.className = "meaning-dialog";
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close(); // клик по затемнению
    });
    document.body.append(dialog);
  }

  const title = document.createElement("h2");
  title.textContent = word;
  const body = document.createElement("div");
  body.textContent = "Загружаем…";
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Закрыть";
  close.addEventListener("click", () => dialog.close());
  dialog.replaceChildren(title, body, close);
  if (!dialog.open) dialog.showModal();

  try {
    const response = await fetch(`/words/${encodeURIComponent(word)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "ошибка сервера");
    const link = Object.assign(document.createElement("a"), {
      href: data.url,
      target: "_blank",
      rel: "noopener",
      textContent: "Статья в Викисловаре",
    });
    if (data.definitions.length === 0) {
      body.replaceChildren("В Викисловаре нет русского значения этого слова. ", link);
      return;
    }
    const list = document.createElement("ol");
    for (const text of data.definitions) {
      list.append(Object.assign(document.createElement("li"), { textContent: text }));
    }
    body.replaceChildren(list, link);
  } catch (error) {
    body.textContent = `Не получилось узнать значение: ${error.message}`;
  }
}

function wordButton(word) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "log-word";
  button.textContent = word;
  button.title = "Что значит это слово";
  button.addEventListener("click", () => showMeaning(word));
  return button;
}

export function renderLog(root, state) {
  const names = new Map(state.players.map((player) => [player.id, player.name]));
  root.replaceChildren(
    ...state.log.map((entry) => {
      const item = document.createElement("li");
      item.className = `log-entry log-${entry.type}`;
      if (entry.type === "move" && entry.words) {
        // слова хода — кнопки: по клику показываем значение
        item.append(`${names.get(entry.player) ?? ""}: `);
        entry.words.forEach(([word], index) => {
          if (index) item.append(", ");
          item.append(wordButton(word));
        });
        item.append(` — ${entry.score}`);
      } else {
        item.textContent = entry.text;
      }
      return item;
    })
  );
  root.scrollTop = root.scrollHeight;
}

// Кнопка «Добавить в словарь» рядом с отказом: правка свободная, поэтому
// подтверждение соперника не требуется — спор решается за столом.
export function renderUnknownWords(root, words, onAllow) {
  root.replaceChildren(
    ...words.map((word) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "allow-word";
      button.textContent = `Добавить «${word}» в словарь`;
      button.addEventListener("click", () => onAllow(word));
      return button;
    })
  );
}

// Мешок и стойка соперника приходят одним счётчиком: что именно лежит
// у соперника, сервер не сообщает.
export function renderUnseen(root, state) {
  const total = state.unseen.reduce((sum, item) => sum + item.count, 0);
  const theirs = state.players
    .filter((player) => !player.is_you)
    .reduce((sum, player) => sum + player.tiles, 0);

  const summary = document.createElement("p");
  summary.className = "unseen-summary";
  summary.textContent = `Ещё не вышли: ${total} (в мешке ${state.bag}, у соперника ${theirs})`;

  const grid = document.createElement("div");
  grid.className = "unseen-grid";
  // в наборе буквы идут по частоте, искать удобнее по алфавиту; пустышка в конце
  const items = [...state.unseen].sort((a, b) => {
    if (a.letter === null) return 1;
    if (b.letter === null) return -1;
    return a.letter.localeCompare(b.letter, "ru");
  });
  for (const item of items) {
    const tile = document.createElement("span");
    tile.className = "tile unseen-tile";
    if (item.letter === null) tile.classList.add("tile-blank");
    tile.append(
      Object.assign(document.createElement("span"), {
        className: "tile-letter",
        textContent: item.letter ?? "•",
      }),
      Object.assign(document.createElement("sub"), {
        className: "tile-value",
        textContent: item.value ? String(item.value) : "",
      })
    );

    const cell = document.createElement("div");
    cell.className = "unseen-item";
    if (item.count === 0) cell.classList.add("unseen-gone");
    cell.title = item.letter === null ? "пустышка" : item.letter;
    cell.append(
      tile,
      Object.assign(document.createElement("span"), {
        className: "unseen-count",
        textContent: `×${item.count}`,
      })
    );
    grid.append(cell);
  }

  root.replaceChildren(summary, grid);
}

export function askExchange(state) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "exchange-dialog";
    const chosen = new Set();

    const tiles = document.createElement("div");
    tiles.className = "exchange-tiles";
    for (const tile of state.rack) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tile exchange-tile";
      button.textContent = tile.letter ?? "•";
      button.addEventListener("click", () => {
        if (chosen.has(tile.id)) chosen.delete(tile.id);
        else chosen.add(tile.id);
        button.classList.toggle("tile-selected", chosen.has(tile.id));
        confirm.disabled = chosen.size === 0;
      });
      tiles.append(button);
    }

    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.textContent = "Обменять";
    confirm.disabled = true;
    confirm.addEventListener("click", () => {
      dialog.close();
      resolve([...chosen]);
    });

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.textContent = "Отмена";
    cancel.addEventListener("click", () => {
      dialog.close();
      resolve(null);
    });

    const title = document.createElement("p");
    title.textContent = "Какие фишки сдаём? Ход при обмене теряется.";

    const buttons = document.createElement("div");
    buttons.className = "exchange-buttons";
    buttons.append(confirm, cancel);

    dialog.append(title, tiles, buttons);
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    document.body.append(dialog);
    dialog.showModal();
  });
}

const SVG = "http://www.w3.org/2000/svg";
const LINE_COLORS = ["var(--accent)", "var(--tl)", "var(--ok)", "var(--tw)"];

function svg(tag, attributes) {
  const element = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  return element;
}

// График счёта по ходам: по линии на игрока, последняя точка — итог со
// штрафами за остаток фишек.
function scoreChart(timeline, players) {
  const width = 320;
  const height = 130;
  const pad = 6;
  const values = timeline.flat();
  const top = Math.max(1, ...values);
  const bottom = Math.min(0, ...values);
  const x = (i) => pad + (i * (width - 2 * pad)) / Math.max(1, timeline.length - 1);
  const y = (v) => pad + ((top - v) * (height - 2 * pad)) / (top - bottom);

  const chart = svg("svg", {
    viewBox: `0 0 ${width} ${height}`,
    class: "score-chart",
    role: "img",
    "aria-label": "График счёта по ходам",
  });
  chart.append(svg("line", { x1: pad, x2: width - pad, y1: y(0), y2: y(0), class: "chart-zero" }));
  players.forEach((player, index) => {
    const points = timeline.map((row, i) => `${x(i)},${y(row[index])}`).join(" ");
    chart.append(
      svg("polyline", { points, fill: "none", stroke: LINE_COLORS[index], "stroke-width": 2 })
    );
  });
  const topLabel = svg("text", { x: width - pad, y: pad + 8, class: "chart-label" });
  topLabel.textContent = String(top);
  chart.append(topLabel);

  const legend = document.createElement("div");
  legend.className = "chart-legend";
  players.forEach((player, index) => {
    const item = document.createElement("span");
    item.style.setProperty("--series", LINE_COLORS[index]);
    item.textContent = player.name;
    legend.append(item);
  });

  const box = document.createElement("div");
  box.append(chart, legend);
  return box;
}

function statsTable(stats, players) {
  const youById = new Map(players.map((player) => [player.id, player.is_you]));
  const rows = [
    ["Ходов", (s) => s.moves],
    ["В среднем за ход", (s) => s.average],
    ["Лучший ход", (s) => (s.best ? `${s.best.words.join(", ")} — ${s.best.score}` : "—")],
    ["Самое длинное слово", (s) => s.longest ?? "—"],
    ["Бинго (все 7 фишек)", (s) => s.bingos],
    ["Пасы / обмены", (s) => `${s.passes} / ${s.exchanges}`],
  ];

  const table = document.createElement("table");
  table.className = "stats-table";
  const head = table.createTHead().insertRow();
  head.append(document.createElement("th"));
  for (const item of stats.players) {
    const th = document.createElement("th");
    th.textContent = `${item.name}${youById.get(item.id) ? " (вы)" : ""}`;
    head.append(th);
  }
  const body = table.createTBody();
  for (const [label, value] of rows) {
    const row = body.insertRow();
    const th = document.createElement("th");
    th.textContent = label;
    row.append(th);
    for (const item of stats.players) row.insertCell().textContent = String(value(item));
  }
  return table;
}

export function rematchUrl(rematch) {
  return `/g/${rematch.game_id}#${rematch.token}`;
}

// Экран перерисовывается на каждое состояние: реванш может прийти от
// соперника уже после того, как экран показан.
export function renderEndScreen(state, { rematchRequested, onRematch }) {
  let screen = document.getElementById("end-screen");
  if (!screen) {
    screen = document.createElement("div");
    screen.id = "end-screen";
    screen.className = "end-screen";
    document.querySelector(".side").prepend(screen);
  }

  const winners = state.players.filter((player) => state.winners.includes(player.id));
  const verdict =
    winners.length > 1
      ? "Ничья"
      : winners[0]?.is_you
        ? "Вы выиграли"
        : `Выиграл ${winners[0]?.name ?? "никто"}`;

  const title = document.createElement("h2");
  title.textContent = `Партия окончена. ${verdict}`;

  const scores = document.createElement("ul");
  scores.className = "end-scores";
  for (const player of state.players) {
    const item = document.createElement("li");
    item.textContent = `${player.name}${player.is_you ? " (вы)" : ""}: ${player.score}`;
    scores.append(item);
  }

  const actions = document.createElement("div");
  actions.className = "end-actions";
  if (state.rematch) {
    const go = document.createElement("a");
    go.className = "button-link";
    go.href = rematchUrl(state.rematch);
    go.textContent = "Перейти к реваншу";
    actions.append(go);
  } else {
    const again = document.createElement("button");
    again.type = "button";
    again.textContent = rematchRequested ? "Создаём…" : "Сыграть ещё";
    again.disabled = rematchRequested;
    again.addEventListener("click", onRematch);
    actions.append(again);
  }
  const fresh = document.createElement("a");
  fresh.href = "/";
  fresh.textContent = "Новая партия с нуля";
  actions.append(fresh);

  screen.replaceChildren(title, scores, actions);
  if (state.stats) {
    const heading = document.createElement("h3");
    heading.textContent = "Итоги";
    screen.append(
      heading,
      statsTable(state.stats, state.players),
      scoreChart(state.stats.timeline, state.stats.players)
    );
  }
}
