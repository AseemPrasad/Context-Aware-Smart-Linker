let aiBtn = null;
let tooltip = null;

let cachedText = "";
let activeTooltipTimer = null;
let currentSelectionSeq = 0;

function clearTooltipTimer() {
  if (activeTooltipTimer) {
    clearTimeout(activeTooltipTimer);
    activeTooltipTimer = null;
  }
}

// Last recorded selection bounding rect for accurate in-viewport positioning
let lastSelectionRect = null;

// Optional tenant identifier for the backend retrieval engine.
// Checks chrome.storage with fallback to 'default'.
let cachedTenantId = "default";
try {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["caslTenantId"], (result) => {
      if (result && result.caslTenantId) {
        cachedTenantId = result.caslTenantId;
      }
    });
  }
} catch (e) {
  // Fail silently and use 'default'
}

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

  lastSelectionRect = rect;
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

  aiBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    currentSelectionSeq++;
    const seq = currentSelectionSeq;
    showTooltip("Thinking… 🤖");

    // Ensure tenantId sync is awaited if chrome.storage is present
    try {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        const stored = await chrome.storage.local.get(["caslTenantId"]);
        if (stored?.caslTenantId) cachedTenantId = stored.caslTenantId;
      }
    } catch (_) {}

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
          if (seq !== currentSelectionSeq) return; // Discard stale race responses
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
  clearTooltipTimer();
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

  const topPos = lastSelectionRect
    ? lastSelectionRect.bottom + window.scrollY + 8
    : window.scrollY + 120;
  const leftPos = lastSelectionRect
    ? Math.max(10, Math.min(window.innerWidth - 340, lastSelectionRect.left + window.scrollX))
    : window.scrollX + 120;

  tooltip.style.top = `${topPos}px`;
  tooltip.style.left = `${leftPos}px`;

  document.body.appendChild(tooltip);

  activeTooltipTimer = setTimeout(() => {
    tooltip?.remove();
    activeTooltipTimer = null;
  }, 12000);
}

function showTooltip(text) {
  clearTooltipTimer();
  tooltip?.remove();

  tooltip = document.createElement("div");
  tooltip.className = "casl-tooltip";
  tooltip.textContent = text;

  const topPos = lastSelectionRect
    ? lastSelectionRect.bottom + window.scrollY + 8
    : window.scrollY + 120;
  const leftPos = lastSelectionRect
    ? Math.max(10, Math.min(window.innerWidth - 340, lastSelectionRect.left + window.scrollX))
    : window.scrollX + 120;

  tooltip.style.top = `${topPos}px`;
  tooltip.style.left = `${leftPos}px`;

  document.body.appendChild(tooltip);

  activeTooltipTimer = setTimeout(() => {
    tooltip?.remove();
    activeTooltipTimer = null;
  }, 8000);
}

window.addEventListener("beforeunload", () => {
  aiBtn?.remove();
  tooltip?.remove();
});
