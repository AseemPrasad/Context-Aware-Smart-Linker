// Optional developer personal Groq fallback key (empty by default for security).
// Users can configure their own key via Options page if desired.
const GROQ_API_KEY = "";

// Backend endpoint for the hybrid RAG & Due Diligence research engine.
// Defaults to local backend; configurable via the Extension Options page.
const BACKEND_BASE_URL = "http://localhost:8000";

console.log("✅ CASL background loaded");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("📩 Message received in background:", message);

  if (message.type !== "EXPLAIN") {
    sendResponse({ explanation: "Unknown message type" });
    return;
  }

  (async () => {
    try {
      const result = await explain(message.payload);
      if (typeof result === "object" && result !== null) {
        sendResponse({
          explanation: result.explanation || result.executive_summary || "",
          structured: result
        });
      } else {
        sendResponse({ explanation: result });
      }
    } catch (err) {
      console.error("❌ Explanation error:", err);
      sendResponse({ explanation: "Explanation request failed" });
    }
  })();

  return true; // 🔑 REQUIRED
});

// Try the backend hybrid RAG engine first; fall back to direct Groq.
async function explain(payload) {
  if (BACKEND_BASE_URL) {
    try {
      return await explainWithBackend(payload);
    } catch (err) {
      console.warn("⚠️ Backend unavailable, falling back to Groq:", err);
    }
  }
  return await explainWithGroq(payload); // original behavior when unset/down
}

// Calls the backend due-diligence engine and returns its structured response.
async function explainWithBackend({ term, title, paragraph, tenantId }) {
  let targetUrl = BACKEND_BASE_URL;
  let headers = { "Content-Type": "application/json" };
  let resolvedTenant = tenantId || "default";

  // Check custom enterprise settings if available
  try {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      const cfg = await chrome.storage.local.get(["caslGatewayUrl", "caslTenantId", "caslApiKey"]);
      if (cfg.caslGatewayUrl) targetUrl = cfg.caslGatewayUrl;
      if (cfg.caslTenantId && (!tenantId || tenantId === "default")) resolvedTenant = cfg.caslTenantId;
      if (cfg.caslApiKey) headers["Authorization"] = `Bearer ${cfg.caslApiKey}`;
    }
  } catch (_) {}

  const res = await fetch(`${targetUrl}/api/v1/finance/explain`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({
      term: term,
      surrounding_context: paragraph || "",
      page_title: title || "",
      tenant_id: resolvedTenant,
      strict_citations: true
    }),
  });
  if (res.status === 402) {
    const errorData = await res.json().catch(() => ({}));
    return {
      quotaExceeded: true,
      explanation: errorData.detail || "Monthly research credit quota exceeded. Please contact your administrator.",
      structured: {
        executive_summary: errorData.detail || "Monthly credit quota exceeded. Upgrade your workspace plan to resume research.",
        risk_implications: "Billing hard cap enforced. Credit consumption halted.",
        citations: []
      }
    };
  }
  if (!res.ok) throw new Error(`Backend due-diligence request failed: ${res.status}`);
  const data = await res.json();
  return data;
}

async function explainWithGroq({ term, title, paragraph }) {
  // Check if analyst has configured a personal key in Extension Options
  let activeGroqKey = GROQ_API_KEY;
  try {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      const stored = await chrome.storage.local.get(["caslUserGroqKey"]);
      if (stored?.caslUserGroqKey) activeGroqKey = stored.caslUserGroqKey;
    }
  } catch (_) {}

  // If no personal key is available, return an informative enterprise offline message
  if (!activeGroqKey) {
    return {
      explanation: "CASL Gateway is currently offline. Please contact your workspace administrator or check your connection in Extension Options.",
      structured: {
        executive_summary: "Enterprise Ingress Unreachable: The CASL backend service is offline. Please verify network connectivity or Gateway URL in Extension Settings.",
        risk_implications: "Offline mode active. Real-time regulatory due diligence citations are paused.",
        citations: []
      }
    };
  }

  const prompt = `
Explain the term "${term}" in the context of the webpage titled "${title}".

Surrounding content:
"${paragraph}"

Respond in exactly 2 short, clear sentences.
`;

  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${activeGroqKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.3,
    }),
  });

  const data = await res.json();

  // ✅ PROPER error handling
  if (!res.ok || !data.choices || !data.choices.length) {
    console.error("❌ Groq API error response:", data);
    throw new Error(data?.error?.message || "Groq API failed");
  }

  return data.choices[0].message.content.trim();
}
