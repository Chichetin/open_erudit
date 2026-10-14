// Части интерфейса, не связанные с доской: журнал, диалог обмена,
// предложение добавить слово в словарь, оставшиеся буквы, экран конца партии.

export function renderLog(root, state) {
  root.replaceChildren(
    ...state.log.map((entry) => {
      const item = document.createElement("li");
      item.className = `log-entry log-${entry.type}`;
      item.textContent = entry.text;
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

export function renderEndScreen(state) {
  if (document.getElementById("end-screen")) return;

  const winners = state.players.filter((player) => state.winners.includes(player.id));
  const verdict =
    winners.length > 1
      ? "Ничья"
      : winners[0]?.is_you
        ? "Вы выиграли"
        : `Выиграл ${winners[0]?.name ?? "никто"}`;

  const screen = document.createElement("div");
  screen.id = "end-screen";
  screen.className = "end-screen";

  const title = document.createElement("h2");
  title.textContent = `Партия окончена. ${verdict}`;

  const scores = document.createElement("ul");
  scores.className = "end-scores";
  for (const player of state.players) {
    const item = document.createElement("li");
    item.textContent = `${player.name}${player.is_you ? " (вы)" : ""}: ${player.score}`;
    scores.append(item);
  }

  const again = document.createElement("a");
  again.href = "/";
  again.textContent = "Новая партия";

  screen.append(title, scores, again);
  document.querySelector(".side").prepend(screen);
}
