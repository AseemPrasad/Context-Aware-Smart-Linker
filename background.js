const GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE";

// Backend endpoint for the hybrid RAG & Due Diligence research engine.
// Defaults to local backend; automatically falls back to Groq if unreachable.
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
  const res = await fetch(`${BACKEND_BASE_URL}/api/v1/finance/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      term: term,
      surrounding_context: paragraph || "",
      page_title: title || "",
      tenant_id: tenantId || "default",
      strict_citations: true
    }),
  });
  if (!res.ok) throw new Error(`Backend due-diligence request failed: ${res.status}`);
  const data = await res.json();
  return data;
}

async function explainWithGroq({ term, title, paragraph }) {
  const prompt = `
Explain the term "${term}" in the context of the webpage titled "${title}".

Surrounding content:
"${paragraph}"

Respond in exactly 2 short, clear sentences.
`;

  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${GROQ_API_KEY}`,
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
