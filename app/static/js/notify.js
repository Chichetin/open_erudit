// Оповещение о ходе: заголовок вкладки всегда показывает, чей ход, а когда
// ход переходит к игроку — тихий сигнал и, если вкладка в фоне, системное
// уведомление. Колокольчик в шапке выключает звук и уведомления.

const STORAGE_KEY = "erudit:notify";

function loadEnabled() {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "off";
  } catch {
    return true;
  }
}

function saveEnabled(enabled) {
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
  } catch {
    // не сохранили — до перезагрузки и так работает
  }
}

let audio = null;

// Браузер разрешает звук только после действия игрока на странице; до
// первого клика сигнал просто не прозвучит.
function beep() {
  try {
    audio ??= new AudioContext();
    const now = audio.currentTime;
    for (const [offset, frequency] of [[0, 660], [0.14, 880]]) {
      const tone = audio.createOscillator();
      const volume = audio.createGain();
      tone.frequency.value = frequency;
      volume.gain.setValueAtTime(0.0001, now + offset);
      volume.gain.exponentialRampToValueAtTime(0.12, now + offset + 0.02);
      volume.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.18);
      tone.connect(volume).connect(audio.destination);
      tone.start(now + offset);
      tone.stop(now + offset + 0.2);
    }
  } catch {
    // нет звука — не беда
  }
}

function systemNotification() {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    const note = new Notification("Эрудит", {
      body: "Ваш ход",
      icon: "/static/apple-touch-icon.png",
      tag: "erudit-turn",
    });
    note.addEventListener("click", () => {
      window.focus();
      note.close();
    });
  } catch {
    // мобильные браузеры не дают создавать уведомления из страницы
  }
}

export function createTurnNotifier(button) {
  let enabled = loadEnabled();
  let wasMyTurn = null;

  function renderButton() {
    button.textContent = enabled ? "🔔" : "🔕";
    button.title = enabled
      ? "Звук и уведомления о ходе включены"
      : "Звук и уведомления о ходе выключены";
    button.setAttribute("aria-pressed", String(enabled));
  }

  button.addEventListener("click", () => {
    enabled = !enabled;
    saveEnabled(enabled);
    renderButton();
    if (enabled && "Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  });
  renderButton();

  return {
    update(state) {
      const myTurn = state.status === "active" && state.your_turn;
      if (state.status === "finished") {
        document.title = "Партия окончена — Эрудит";
      } else {
        document.title = myTurn ? "● Ваш ход — Эрудит" : "Ход соперника — Эрудит";
      }

      // первое состояние после загрузки — не событие, сигналить не о чем
      if (wasMyTurn === false && myTurn && enabled) {
        beep();
        if (document.hidden) systemNotification();
      }
      wasMyTurn = myTurn;
    },
  };
}
