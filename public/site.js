const agendaElement = document.querySelector("#agenda");
const eventTemplate = document.querySelector("#event-template");
const subscribeLink = document.querySelector("#subscribe-link");
const dateJumpElement = document.querySelector("#date-jump");

let allEvents = [];

const dateFormatter = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Amsterdam",
});

const allDayFormatter = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Europe/Amsterdam",
});

const dayFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  timeZone: "Europe/Amsterdam",
});

const monthFormatter = new Intl.DateTimeFormat("en-GB", {
  month: "short",
  timeZone: "Europe/Amsterdam",
});

async function init() {
  try {
    const response = await fetch("pruts-agenda.ics", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load feed: ${response.status}`);
    }

    allEvents = parseIcs(await response.text())
      .filter((event) => event.end >= startOfToday())
      .sort((a, b) => a.start - b.start);

    if (allEvents[0]) {
      dateJumpElement.min = toDateInputValue(allEvents[0].start);
      dateJumpElement.value = toDateInputValue(allEvents[0].start);
    }
    renderAgenda();
  } catch (error) {
    agendaElement.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function parseIcs(feed) {
  return eventBlocks(unfoldLines(feed)).map((block) => {
    const categories = splitList(block.CATEGORIES || "");
    const source = eventSource(categories, block.URL || "");
    return {
      title: block.SUMMARY || "Untitled event",
      start: parseIcsDate(block.DTSTART || "", block.DTSTART_VALUE === "DATE"),
      end: parseIcsDate(block.DTEND || block.DTSTART || "", block.DTEND_VALUE === "DATE"),
      allDay: block.DTSTART_VALUE === "DATE",
      description: block.DESCRIPTION || "",
      location: block.LOCATION || "",
      url: block.URL || "",
      categories,
      source,
    };
  });
}

function unfoldLines(feed) {
  const lines = [];
  for (const line of feed.split(/\r?\n/)) {
    if (/^[ \t]/.test(line) && lines.length) {
      lines[lines.length - 1] += line.slice(1);
    } else {
      lines.push(line);
    }
  }
  return lines;
}

function eventBlocks(lines) {
  const blocks = [];
  let current = null;

  for (const line of lines) {
    if (line === "BEGIN:VEVENT") {
      current = {};
      continue;
    }
    if (line === "END:VEVENT") {
      if (current) {
        blocks.push(current);
      }
      current = null;
      continue;
    }
    if (!current || !line.includes(":")) {
      continue;
    }

    const [rawName, ...valueParts] = line.split(":");
    const value = unescapeIcs(valueParts.join(":"));
    const [name, ...params] = rawName.split(";");
    current[name] = value;
    for (const param of params) {
      const [paramName, paramValue] = param.split("=");
      if (paramName && paramValue) {
        current[`${name}_${paramName}`] = paramValue;
      }
    }
  }

  return blocks;
}

function parseIcsDate(value, allDay) {
  if (allDay) {
    return new Date(`${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}T00:00:00`);
  }

  const match = value.match(
    /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?$/
  );
  if (!match) {
    return new Date();
  }

  const [, year, month, day, hour, minute, second] = match;
  return new Date(Date.UTC(year, Number(month) - 1, day, hour, minute, second));
}

function renderAgenda() {
  if (!allEvents.length) {
    agendaElement.innerHTML = '<p class="empty">No upcoming events.</p>';
    return;
  }

  agendaElement.replaceChildren(...allEvents.map(renderEvent));
}

function renderEvent(event, index) {
  const node = eventTemplate.content.firstElementChild.cloneNode(true);
  node.id = `event-${index}`;
  node.dataset.start = toDateInputValue(event.start);
  if (event.url) {
    node.classList.add("is-clickable");
    node.tabIndex = 0;
    node.setAttribute("role", "link");
    node.setAttribute("aria-label", `Open details for ${event.title}`);
    node.addEventListener("click", () => {
      window.open(event.url, "_blank", "noreferrer");
    });
    node.addEventListener("keydown", (keyboardEvent) => {
      if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
        keyboardEvent.preventDefault();
        window.open(event.url, "_blank", "noreferrer");
      }
    });
  }

  const date = node.querySelector(".event-date");
  date.dateTime = event.start.toISOString();
  date.replaceChildren(
    element("span", monthFormatter.format(event.start)),
    element("span", dayFormatter.format(event.start))
  );

  node.querySelector("h2").textContent = event.title;
  node.querySelector(".event-time").textContent = eventTime(event);

  const location = node.querySelector(".event-location");
  location.textContent = event.location;
  location.hidden = !event.location;

  const description = node.querySelector(".event-description");
  description.textContent = truncate(event.description, 240);
  description.hidden = !event.description;

  const tags = displayTags(event);
  const tagsElement = node.querySelector(".event-tags");
  tagsElement.hidden = !tags.length && event.source === "Manual";
  tagsElement.replaceChildren(
    ...tags.map((tag) => element("span", tag, "tag")),
    ...(event.source === "Manual" ? [] : [element("span", event.source, "event-source")])
  );

  node.querySelector(".event-source[hidden]")?.remove();

  return node;
}

function eventSource(categories, url) {
  const sourceLabels = {
    Waag: "Waag",
    "The Hmm": "The Hmm",
    "Hackers & Designers": "Hackers & Designers",
    Radar: "Radar Squad",
    "Radar Squad": "Radar Squad",
    "Critical Infrastructure Lab": "Critical Infrastructure Lab",
  };
  const categorySource = categories.find((category) => category in sourceLabels);
  if (categorySource) {
    return sourceLabels[categorySource];
  }

  if (url.includes("thehmm.nl")) {
    return "The Hmm";
  }
  if (url.includes("waag.org")) {
    return "Waag";
  }
  if (url.includes("hackersanddesigners.nl")) {
    return "Hackers & Designers";
  }
  if (url.includes("radar.squat.net")) {
    return "Radar Squad";
  }
  if (url.includes("criticalinfralab.net")) {
    return "Critical Infrastructure Lab";
  }

  return "Manual";
}

function displayTags(event) {
  const tags = event.categories.filter((category) => category !== event.source);
  return tags;
}

function eventTime(event) {
  if (event.allDay) {
    return allDayRange(event);
  }

  return dateFormatter.format(event.start);
}

function allDayRange(event) {
  const end = new Date(event.end);
  end.setDate(end.getDate() - 1);

  if (toDateInputValue(event.start) === toDateInputValue(end)) {
    return allDayFormatter.format(event.start);
  }

  const startText = allDayFormatter.format(event.start);
  const endText = allDayFormatter.format(end);
  return `${startText} - ${endText}`;
}

function splitList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function unescapeIcs(value) {
  return value
    .replace(/\\n/g, "\n")
    .replace(/\\N/g, "\n")
    .replace(/\\,/g, ",")
    .replace(/\\;/g, ";")
    .replace(/\\\\/g, "\\");
}

function startOfToday() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function jumpToDate(value) {
  if (!value || !allEvents.length) {
    return;
  }

  const index = allEvents.findIndex((event) => {
    return toDateInputValue(event.start) >= value;
  });
  const targetIndex = index === -1 ? allEvents.length - 1 : index;
  document.querySelector(`#event-${targetIndex}`)?.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

function toDateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function truncate(value, maxLength) {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) {
    return compact;
  }
  return `${compact.slice(0, maxLength - 1)}...`;
}

function element(tagName, text, className) {
  const node = document.createElement(tagName);
  node.textContent = text;
  if (className) {
    node.className = className;
  }
  return node;
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

init();

dateJumpElement.addEventListener("change", () => {
  jumpToDate(dateJumpElement.value);
});

if (location.protocol.startsWith("http")) {
  const feedUrl = new URL("pruts-agenda.ics", location.href);
  subscribeLink.href = `webcal://${feedUrl.host}${feedUrl.pathname}`;
}
