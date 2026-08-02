const button = document.getElementById("create");
const links = document.getElementById("links");
const list = document.getElementById("link-list");
const error = document.getElementById("error");

button.addEventListener("click", async () => {
  button.disabled = true;
  error.hidden = true;
  try {
    const response = await fetch("/games", { method: "POST" });
    if (!response.ok) throw new Error("сервер отказал");
    const data = await response.json();
    list.replaceChildren(
      ...data.links.map((url, i) => {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = url;
        link.textContent = url;
        item.append(i === 0 ? "Вы: " : "Соперник: ", link);
        return item;
      })
    );
    links.hidden = false;
  } catch (e) {
    error.textContent = `Не получилось создать партию: ${e.message}`;
    error.hidden = false;
  } finally {
    button.disabled = false;
  }
});
