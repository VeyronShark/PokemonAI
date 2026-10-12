const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const welcome = document.querySelector("#welcome");
const errorMessage = document.querySelector("#error-message");

const history = [];
let isSending = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function safeImageUrl(value) {
  if (typeof value !== "string") return "";
  const normalized = value.replace(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/, "$2");
  try {
    const url = new URL(normalized);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch {
    return "";
  }
}

function addImage(container, url, alt, className) {
  const safeUrl = safeImageUrl(url);
  if (!safeUrl) return null;
  const image = element("img", className);
  image.src = safeUrl;
  image.alt = alt;
  image.loading = "lazy";
  image.addEventListener("error", () => image.remove(), { once: true });
  container.append(image);
  return image;
}

function renderTeam(container, team) {
  if (!Array.isArray(team) || team.length === 0) return;
  const card = element("div", "result-card team-grid");
  for (const member of team) {
    if (!member || typeof member !== "object") continue;
    const item = element("div", "team-member");
    addImage(item, member.showdown_sprite, `${member.name || "Pokémon"} sprite`);
    item.append(element("span", "", String(member.name || "Pokémon")));
    card.append(item);
  }
  if (card.childElementCount) container.append(card);
}

function renderCharacterSheet(container, sheet) {
  if (!sheet || typeof sheet !== "object") return;
  const card = element("div", "result-card");
  const heading = element("div", "sheet-heading");
  const sprite = sheet.sprites?.other?.["official-artwork"]?.front_default
    || sheet.sprites?.front_default;
  addImage(heading, sprite, `${sheet.name || "Pokémon"} artwork`);
  const title = element("div");
  title.append(element("h2", "", String(sheet.name || "Pokémon")));
  const types = Array.isArray(sheet.types)
    ? sheet.types.map((item) => item?.type?.name).filter(Boolean)
    : [];
  const typeList = element("div", "type-list");
  types.forEach((type) => typeList.append(element("span", "pill", type)));
  title.append(typeList);
  heading.append(title);
  card.append(heading);

  const abilities = Array.isArray(sheet.abilities)
    ? sheet.abilities.map((item) => item?.ability?.name).filter(Boolean)
    : [];
  if (abilities.length) {
    card.append(element("p", "sheet-subtitle", "Abilities"));
    const abilityList = element("div", "ability-list");
    abilities.forEach((name) => abilityList.append(element("span", "pill", name)));
    card.append(abilityList);
  }

  if (Array.isArray(sheet.stats) && sheet.stats.length) {
    card.append(element("p", "sheet-subtitle", "Base stats"));
    const stats = element("div", "stats-list");
    for (const stat of sheet.stats) {
      const value = Number(stat?.base_stat);
      if (!Number.isFinite(value)) continue;
      const row = element("div", "stat-row");
      row.append(element("span", "", String(stat?.stat?.name || "Stat")));
      row.append(element("span", "", String(value)));
      const track = element("div", "stat-track");
      const fill = element("div", "stat-fill");
      fill.style.width = `${Math.min(value / 255 * 100, 100)}%`;
      track.append(fill);
      row.append(track);
      stats.append(row);
    }
    card.append(stats);
  }
  container.append(card);
}

function renderBattle(container, data) {
  if (!data || typeof data !== "object") return;
  const card = element("div", "result-card");
  const row = element("div", "battle-row");
  const players = [data.player_one, data.player_two];
  players.forEach((player, index) => {
    if (!player || typeof player !== "object") return;
    const side = element("div", "battle-side");
    const spriteUrl = index === 0 ? player.back_sprite : player.front_sprite;
    addImage(side, spriteUrl, `${player.name || "Pokémon"} battle sprite`);
    side.append(element("h3", "", String(player.name || `Player ${index + 1}`)));
    const maxHp = Number(player.max_hp);
    if (Number.isFinite(maxHp) && maxHp > 0) {
      const label = element("div", "hp-label");
      label.append(element("span", "", "Max HP"));
      label.append(element("span", "", String(maxHp)));
      side.append(label);
      const track = element("div", "hp-track");
      const fill = element("div", "hp-fill");
      fill.style.width = "100%";
      track.append(fill);
      side.append(track);
    }
    if (Array.isArray(player.moves)) {
      const moves = element("div", "move-list");
      player.moves.forEach((move) => {
        if (move?.name) moves.append(element("span", "move", String(move.name)));
      });
      side.append(moves);
    }
    row.append(side);
    if (index === 0) row.append(element("span", "battle-vs", "VS"));
  });
  if (row.childElementCount) {
    card.append(row);
    container.append(card);
  }
}

function renderResponseExtras(container, data) {
  switch (data.type) {
    case "pokemon_data":
      addImage(container, data.image_url, "Pokémon official artwork", "result-card pokemon-artwork");
      break;
    case "team_analysis":
      renderTeam(container, data.team_sprites);
      break;
    case "character_sheet":
      renderCharacterSheet(container, data.character_sheet);
      break;
    case "battle_simulation":
      renderBattle(container, data.battle_data);
      break;
  }
}

function addMessage(role, text, responseData) {
  const message = element("article", `message ${role}`);
  const avatar = element("div", "avatar", role === "user" ? "You" : "P");
  avatar.setAttribute("aria-hidden", "true");
  const body = element("div", "message-body");
  body.append(element("p", "message-label", role === "user" ? "You" : "Poké AI"));
  body.append(element("div", "bubble", text));
  if (responseData) renderResponseExtras(body, responseData);
  message.append(avatar, body);
  conversation.append(message);
  message.scrollIntoView({ behavior: "smooth", block: "nearest" });
  return message;
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
}

async function sendMessage(message) {
  if (isSending || !message.trim()) return;
  isSending = true;
  welcome.hidden = true;
  errorMessage.hidden = true;
  sendButton.disabled = true;
  input.disabled = true;

  addMessage("user", message);
  const typingMessage = addMessage("assistant", "Thinking...", null);
  typingMessage.querySelector(".bubble").classList.add("typing");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    if (!response.ok) {
      throw new Error(`The assistant returned an error (${response.status}). Please try again.`);
    }
    const data = await response.json();
    if (typeof data.response !== "string") {
      throw new Error("The assistant returned an unexpected response. Please try again.");
    }

    typingMessage.remove();
    addMessage("assistant", data.response, data);
    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: data.response });
  } catch (error) {
    typingMessage.remove();
    errorMessage.textContent = error instanceof TypeError
      ? "Could not connect to the assistant. Check that the backend is running, then try again."
      : error.message;
    errorMessage.hidden = false;
  } finally {
    isSending = false;
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  resizeInput();
  sendMessage(message);
});

input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt || "";
    resizeInput();
    form.requestSubmit();
  });
});