let aiBtn = null;
let tooltip = null;

let cachedText = "";
let cachedContext = "";

console.log("✅ CASL content script loaded");

document.addEventListener("selectionchange", () => {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return;

  const text = selection.toString().trim();
  if (!text || text.length < 2) return;

  cachedText = text;
  cachedContext =
    selection.anchorNode?.parentElement?.innerText || "";

  let rect;
  try {
    rect = selection.getRangeAt(0).getBoundingClientRect();
  } catch {
    return;
  }

  if (!rect || rect.width === 0 || rect.height === 0) return;

  showButton(rect);
});

function showButton(rect) {
  if (!rect || typeof rect.left !== "number") return;
  if (aiBtn) return;

  aiBtn = document.createElement("div");
  aiBtn.className = "casl-ai-button";
  aiBtn.textContent = "✨ AI";

  aiBtn.style.top = `${rect.bottom + window.scrollY + 6}px`;
  aiBtn.style.left = `${rect.left + window.scrollX}px`;

  aiBtn.addEventListener("mousedown", e => e.preventDefault());

  aiBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    showTooltip("Thinking… 🤖");

    try {
      chrome.runtime.sendMessage(
        {
          type: "EXPLAIN",
          payload: {
            term: cachedText,
            title: document.title,
            paragraph: cachedContext
          }
        },
        (response) => {
          if (chrome.runtime.lastError) {
            showTooltip("Extension reloaded — refresh page");
            return;
          }
          showTooltip(response?.explanation || "No response");
        }
      );
    } catch {
      showTooltip("Please refresh the page");
    }
  });

  document.body.appendChild(aiBtn);
}

function showTooltip(text) {
  tooltip?.remove();

  tooltip = document.createElement("div");
  tooltip.className = "casl-tooltip";
  tooltip.textContent = text;

  tooltip.style.top = `${window.scrollY + 120}px`;
  tooltip.style.left = `${window.scrollX + 120}px`;

  document.body.appendChild(tooltip);

  setTimeout(() => tooltip?.remove(), 8000);
}

window.addEventListener("beforeunload", () => {
  aiBtn?.remove();
  tooltip?.remove();
});