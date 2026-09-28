// Quick entry: arrow keys select a hit, Enter records the pick, Escape clears.
document.addEventListener("keydown", (event) => {
  const input = document.getElementById("quick");
  if (!input || event.target !== input) return;
  const box = document.getElementById("quick-results");
  const items = Array.from(box.querySelectorAll("button:not([disabled])"));
  if (event.key === "Escape") {
    input.value = "";
    box.innerHTML = "";
    return;
  }
  if (!items.length) return;
  let i = items.findIndex((b) => b.classList.contains("active"));
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    if (i >= 0) items[i].classList.remove("active");
    i = event.key === "ArrowDown" ? Math.min(items.length - 1, i + 1) : Math.max(0, i - 1);
    items[i].classList.add("active");
    items[i].scrollIntoView({ block: "nearest" });
  } else if (event.key === "Enter") {
    event.preventDefault();
    items[i >= 0 ? i : 0].click();
  }
});

// After a pick: clear the quick entry and keep the cursor there on bigger screens.
document.addEventListener("htmx:afterRequest", (event) => {
  const path = (event.detail.pathInfo && event.detail.pathInfo.requestPath) || "";
  if (!path.endsWith("/pick") || !event.detail.successful) return;
  const input = document.getElementById("quick");
  const box = document.getElementById("quick-results");
  const setup = document.querySelector("details.setup");
  if (setup) setup.open = false;
  if (box) box.innerHTML = "";
  if (input) {
    input.value = "";
    if (window.matchMedia("(min-width: 761px)").matches) input.focus();
  }
});

// Player pool: position chips and "show more".
document.addEventListener("click", (event) => {
  const chip = event.target.closest("#pos-chips .chip");
  if (!chip) return;
  document.querySelectorAll("#pos-chips .chip").forEach((c) => c.classList.toggle("on", c === chip));
  document.getElementById("pool-pos").value = chip.dataset.pos;
  document.getElementById("pool-limit").value = 60;
  htmx.trigger("#pool-filters", "pool-change");
});

function morePool() {
  const limit = document.getElementById("pool-limit");
  limit.value = parseInt(limit.value || "60", 10) + 60;
  htmx.trigger("#pool-filters", "pool-change");
}
