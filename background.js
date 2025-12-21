const GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE";

console.log("✅ CASL background loaded");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("📩 Message received in background:", message);

  if (message.type !== "EXPLAIN") {
    sendResponse({ explanation: "Unknown message type" });
    return;
  }

  (async () => {
    try {
      const explanation = await explainWithGroq(message.payload);
      sendResponse({ explanation });
    } catch (err) {
      console.error("❌ Groq error:", err);
      sendResponse({ explanation: "Groq request failed" });
    }
  })();

  return true; // 🔑 REQUIRED
});

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
      "Authorization": `Bearer ${GROQ_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.3
    })
  });

  const data = await res.json();

  // ✅ PROPER error handling
  if (!res.ok || !data.choices || !data.choices.length) {
    console.error("❌ Groq API error response:", data);
    throw new Error(data?.error?.message || "Groq API failed");
  }

  return data.choices[0].message.content.trim();
}