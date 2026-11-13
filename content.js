let aiBtn = null;
let tooltip = null;

let cachedText = "";
let cachedContext = "";

// Optional tenant identifier for the backend retrieval engine.
// Current behavior is unchanged when left as the default.
let cachedTenantId = "default";

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
            paragraph: cachedContext,
            tenantId: cachedTenantId
          }
        },
        (response) => {
          if (chrome.runtime.lastError) {
            showTooltip("Extension reloaded — refresh page");
            return;
          }
          if (response?.structured && response.structured.executive_summary) {
            showStructuredTooltip(response.structured);
          } else {
            showTooltip(response?.explanation || "No response");
          }
        }
      );
    } catch {
      showTooltip("Please refresh the page");
    }
  });

  document.body.appendChild(aiBtn);
}

function showStructuredTooltip(data) {
  tooltip?.remove();

  tooltip = document.createElement("div");
  tooltip.className = "casl-tooltip";

  const header = document.createElement("div");
  header.className = "casl-diligence-header";
  header.textContent = `CASL Verified • ${data.term || "Term"}`;
  tooltip.appendChild(header);

  const summary = document.createElement("div");
  summary.textContent = data.executive_summary;
  tooltip.appendChild(summary);

  if (data.risk_implications) {
    const risk = document.createElement("div");
    risk.style.marginTop = "6px";
    risk.style.fontSize = "11px";
    risk.style.color = "#fca5a5";
    risk.textContent = `Risk: ${data.risk_implications}`;
    tooltip.appendChild(risk);
  }

  if (Array.isArray(data.citations) && data.citations.length > 0) {
    const citationContainer = document.createElement("div");
    citationContainer.className = "casl-citation-container";
    citationContainer.textContent = "Sources: ";

    data.citations.forEach(c => {
      const pill = document.createElement("a");
      pill.className = "casl-citation-pill";
      pill.textContent = `${c.ticker || "SEC"} ${c.section || c.form_type || "Filing"}`;
      pill.title = c.excerpt || "";
      if (c.source_url) {
        pill.href = c.source_url;
        pill.target = "_blank";
      } else {
        pill.href = "#";
        pill.addEventListener("click", (e) => e.preventDefault());
      }
      citationContainer.appendChild(pill);
    });

    tooltip.appendChild(citationContainer);
  }

  tooltip.style.top = `${window.scrollY + 120}px`;
  tooltip.style.left = `${window.scrollX + 120}px`;

  document.body.appendChild(tooltip);

  setTimeout(() => tooltip?.remove(), 12000);
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
