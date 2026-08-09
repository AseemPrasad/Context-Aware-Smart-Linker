const GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE";

// Optional backend endpoint for the hybrid RAG retrieval engine.
// When configured, the extension will query the backend first and fall back
// to the direct Groq call if the backend is unreachable. Leaving this empty
// keeps the original behavior unchanged.
const BACKEND_BASE_URL = ""; // e.g. "https://your-backend.example.com"

console.log("✅ CASL background loaded");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("📩 Message received in background:", message);

  if (message.type !== "EXPLAIN") {
    sendResponse({ explanation: "Unknown message type" });
    return;
  }

  (async () => {
    try {
      const explanation = await explain(message.payload);
      sendResponse({ explanation });
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

// Calls the backend retrieval engine and returns its explanation.
async function explainWithBackend({ term, title, paragraph, tenantId }) {
  const res = await fetch(`${BACKEND_BASE_URL}/api/v1/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tenant_id: tenantId || "default",
      query: term,
      top_k: 50,
      use_rerank: true,
    }),
  });
  if (!res.ok) throw new Error(`Backend search failed: ${res.status}`);
  const data = await res.json();
  const context = (data.hits || []).map((h) => h.passage).join("\n\n");
  return context || "No relevant context found.";
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
