const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const welcome = document.querySelector("#welcome");
const errorMessage = document.querySelector("#error-message");
const assistantLogoUrl = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcShi1ZGHPZJ0tlua41UfrKeHXvcvGIg1c7msaZK7dNAhw&s=10";
const architectureModal = document.querySelector("#architecture-modal");
const architectureOpen = document.querySelector("#architecture-open");
const architectureClose = document.querySelector("#architecture-close");
const architectureDismiss = document.querySelector("#architecture-dismiss");

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
  const parsedUrl = new URL(safeUrl);
  const isPokemonSprite = parsedUrl.hostname === "raw.githubusercontent.com"
    && parsedUrl.pathname.startsWith("/PokeAPI/sprites/master/sprites/pokemon/");
  image.src = isPokemonSprite
    ? `/sprite?url=${encodeURIComponent(parsedUrl.href)}`
    : safeUrl;
  image.alt = alt;
  image.loading = "lazy";
  image.addEventListener("error", () => image.remove(), { once: true });
  container.append(image);
  return image;
}

function cropTransparentSprite(image) {
  if (!image.naturalWidth || !image.naturalHeight) return;

  try {
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return;
    context.drawImage(image, 0, 0);

    const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
    let left = canvas.width;
    let top = canvas.height;
    let right = -1;
    let bottom = -1;
    for (let y = 0; y < canvas.height; y += 1) {
      for (let x = 0; x < canvas.width; x += 1) {
        if (data[(y * canvas.width + x) * 4 + 3] === 0) continue;
        left = Math.min(left, x);
        top = Math.min(top, y);
        right = Math.max(right, x);
        bottom = Math.max(bottom, y);
      }
    }
    if (right < left || bottom < top) return;

    const frame = element("span", "battle-sprite-frame");
    frame.style.width = `${right - left + 1}px`;
    frame.style.height = `${bottom - top + 1}px`;
    frame.setAttribute("role", "img");
    frame.setAttribute("aria-label", image.alt);
    image.alt = "";
    image.style.width = `${canvas.width}px`;
    image.style.height = `${canvas.height}px`;
    image.style.left = `${-left}px`;
    image.style.top = `${-top}px`;
    image.replaceWith(frame);
    frame.append(image);
  } catch (error) {
    console.warn("Could not crop transparent Pokémon sprite margins.", error);
  }
}

function addBattleSprite(container, url, alt) {
  const spriteArea = element("div", "battle-sprite-area");
  const image = addImage(spriteArea, url, alt, "battle-sprite");
  if (!image) return;
  container.append(spriteArea);
  if (image.complete) cropTransparentSprite(image);
  else image.addEventListener("load", () => cropTransparentSprite(image), { once: true });
}

function appendInlineMarkdown(parent, text) {
  const tokenPattern = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|__([^_]+)__|~~([^~]+)~~|\*([^*]+)\*|_([^_]+)_)/g;
  let lastIndex = 0;
  for (const match of text.matchAll(tokenPattern)) {
    const index = match.index ?? 0;
    parent.append(document.createTextNode(text.slice(lastIndex, index)));
    let node;
    if (match[2] && match[3]) {
      const linkUrl = safeImageUrl(match[3]);
      if (linkUrl) {
        node = element("a", "", match[2]);
        node.href = linkUrl;
        node.target = "_blank";
        node.rel = "noopener noreferrer";
      }
    } else if (match[4] !== undefined) {
      node = element("code", "", match[4]);
    } else if (match[5] !== undefined || match[6] !== undefined) {
      node = element("strong", "", match[5] ?? match[6]);
    } else if (match[7] !== undefined) {
      node = element("del", "", match[7]);
    } else if (match[8] !== undefined || match[9] !== undefined) {
      node = element("em", "", match[8] ?? match[9]);
    }
    parent.append(node || document.createTextNode(match[0]));
    lastIndex = index + match[0].length;
  }
  parent.append(document.createTextNode(text.slice(lastIndex)));
}

function renderMarkdown(markdown) {
  const fragment = document.createDocumentFragment();
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (/^\s*```/.test(line)) {
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^\s*```/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = element("pre");
      pre.append(element("code", "", codeLines.join("\n")));
      fragment.append(pre);
      continue;
    }

    const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const node = element(`h${heading[1].length}`);
      appendInlineMarkdown(node, heading[2]);
      fragment.append(node);
      index += 1;
      continue;
    }

    if (/^\s{0,3}(---+|___+|\*\*\*+)\s*$/.test(line)) {
      fragment.append(element("hr"));
      index += 1;
      continue;
    }

    const listMatch = line.match(/^\s*(?:[-*+]|\d+[.)])\s+(.+)$/);
    if (listMatch) {
      const ordered = /^\s*\d/.test(line);
      const list = element(ordered ? "ol" : "ul");
      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*(?:[-*+]|\d+[.)])\s+(.+)$/);
        if (!itemMatch || /^\s*\d/.test(lines[index]) !== ordered) break;
        const item = element("li");
        appendInlineMarkdown(item, itemMatch[1]);
        list.append(item);
        index += 1;
      }
      fragment.append(list);
      continue;
    }

    const quote = line.match(/^\s{0,3}>\s?(.*)$/);
    if (quote) {
      const blockquote = element("blockquote");
      appendInlineMarkdown(blockquote, quote[1]);
      fragment.append(blockquote);
      index += 1;
      continue;
    }

    const paragraphLines = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim()
      && !/^\s*```/.test(lines[index])
      && !/^\s{0,3}#{1,6}\s+/.test(lines[index])
      && !/^\s*(?:[-*+]|\d+[.)])\s+/.test(lines[index])
      && !/^\s{0,3}>/.test(lines[index])
      && !/^\s{0,3}(---+|___+|\*\*\*+)\s*$/.test(lines[index])) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = element("p");
    appendInlineMarkdown(paragraph, paragraphLines.join("\n"));
    fragment.append(paragraph);
  }
  return fragment;
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

function renderBattle(container, data) {
  if (!data || typeof data !== "object") return;
  const card = element("div", "result-card");
  const row = element("div", "battle-row");
  const players = [data.player_one, data.player_two];
  const fighters = [];
  players.forEach((player, index) => {
    if (!player || typeof player !== "object") return;
    const side = element("div", "battle-side");
    const spriteUrl = index === 0 ? player.back_sprite : player.front_sprite;
    addBattleSprite(side, spriteUrl, `${player.name || "Pokémon"} battle sprite`);
    side.append(element("h3", "", String(player.name || `Player ${index + 1}`)));
    const maxHp = Number(player.max_hp);
    const label = element("div", "hp-label");
    label.append(element("span", "", "HP"));
    const hpValue = element("span", "", String(Number.isFinite(maxHp) ? maxHp : 0));
    label.append(hpValue);
    side.append(label);
    const track = element("div", "hp-track");
    const fill = element("div", "hp-fill");
    track.append(fill);
    side.append(track);

    const maxDamage = Array.isArray(player.moves)
      ? Math.max(0, ...player.moves.map((move) => Number(move?.damage_to_opponent) || 0))
      : 0;
    if (Array.isArray(player.moves)) {
      const moves = element("div", "move-list");
      player.moves.forEach((move) => {
        if (move?.name) {
          const damage = Number(move.damage_to_opponent);
          const moveLabel = Number.isFinite(damage)
            ? `${move.name} · ${damage} dmg`
            : String(move.name);
          moves.append(element("span", "move", moveLabel));
        }
      });
      side.append(moves);
    }
    fighters.push({
      name: String(player.name || `Player ${index + 1}`),
      currentHp: Number.isFinite(maxHp) && maxHp > 0 ? maxHp : 0,
      maxHp: Number.isFinite(maxHp) && maxHp > 0 ? maxHp : 0,
      maxDamage,
      hpValue,
      hpFill: fill,
    });
    row.append(side);
    if (index === 0) row.append(element("span", "battle-vs", "VS"));
  });
  if (row.childElementCount) {
    card.append(row);

    const status = element("p", "battle-status", "Ready when you are.");
    status.setAttribute("aria-live", "polite");
    const startButton = element("button", "battle-start", "Start battle");
    startButton.type = "button";
    const canBattle = fighters.length === 2
      && fighters.every((fighter) => fighter.maxHp > 0 && fighter.maxDamage > 0);
    startButton.disabled = !canBattle;
    if (!canBattle) status.textContent = "Battle data is missing valid HP or attack damage.";

    let intervalId;
    const updateHealth = (fighter) => {
      fighter.hpValue.textContent = String(fighter.currentHp);
      fighter.hpFill.style.width = `${fighter.currentHp / fighter.maxHp * 100}%`;
      fighter.hpFill.classList.toggle("hp-low", fighter.currentHp / fighter.maxHp <= 0.25);
    };
    fighters.forEach(updateHealth);

    startButton.addEventListener("click", () => {
      if (!canBattle || intervalId) return;
      startButton.disabled = true;
      startButton.textContent = "Battle in progress";
      status.textContent = "Battle started!";

      intervalId = window.setInterval(() => {
        const [first, second] = fighters;
        first.currentHp = Math.max(0, first.currentHp - second.maxDamage / 2);
        second.currentHp = Math.max(0, second.currentHp - first.maxDamage / 2);
        fighters.forEach(updateHealth);

        const firstFainted = first.currentHp === 0;
        const secondFainted = second.currentHp === 0;
        if (!firstFainted && !secondFainted) {
          status.textContent = "Battle in progress...";
          return;
        }

        window.clearInterval(intervalId);
        intervalId = undefined;
        startButton.textContent = "Battle complete";
        if (firstFainted && secondFainted) {
          status.textContent = "It's a draw! Both Pokémon fainted.";
        } else {
          const winner = firstFainted ? second.name : first.name;
          const capitalizedWinner = winner.charAt(0).toUpperCase() + winner.slice(1);
          status.textContent = `${capitalizedWinner} wins!`;
          status.classList.add("battle-winner");
        }
      }, 1500);
    });

    const controls = element("div", "battle-controls");
    controls.append(status, startButton);
    card.append(controls);
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
    case "battle_simulation":
      renderBattle(container, data.battle_data);
      break;
  }
}

function addMessage(role, text, responseData) {
  const message = element("article", `message ${role}`);
  const avatar = element("div", "avatar", role === "user" ? "You" : "");
  if (role === "assistant") addImage(avatar, assistantLogoUrl, "", "avatar-image");
  avatar.setAttribute("aria-hidden", "true");
  const body = element("div", "message-body");
  body.append(element("p", "message-label", role === "user" ? "You" : "Poké AI"));
  const bubble = element("div", role === "assistant" ? "bubble markdown-body" : "bubble");
  if (role === "assistant") bubble.append(renderMarkdown(text));
  else bubble.textContent = text;
  body.append(bubble);
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
  typingMessage.querySelector(".avatar").classList.add("is-spinning");

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

architectureOpen.addEventListener("click", () => architectureModal.showModal());
architectureClose.addEventListener("click", () => architectureModal.close());
architectureDismiss.addEventListener("click", () => architectureModal.close());
architectureModal.addEventListener("click", (event) => {
  if (event.target === architectureModal) architectureModal.close();
});