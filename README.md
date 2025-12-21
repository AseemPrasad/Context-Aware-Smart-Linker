
CASL (Context-Aware Smart Linker) is a Chrome Extension that provides instant, AI-generated explanations for any highlighted text — without leaving your current tab.

🎯 The Problem

Modern browsing is broken:

You encounter unfamiliar terms, libraries, people, or jargon

You open them in new tabs “to check later”

Tabs pile up → focus breaks → productivity drops


💡 The Solution

CASL eliminates search detours by answering in place:

✨ Key Features

🧠 Context-Aware Explanations
Uses page title + surrounding text to tailor explanations

> “React” on a coding blog ≠ “React” on a chemistry page

⚡ Instant Overlay UI
Floating tooltip (no popup windows, no delays)

🔌 Manifest V3 Compliant
Uses Chrome’s modern service worker architecture

🤖 LLM-Powered (Groq)
Fast, cheap inference using LLaMA-3 via Groq API

🧩 Minimal & Lightweight
No heavy UI frameworks, no page reloads

🛠️ Tech Stack

Chrome Extensions (Manifest V3)
JavaScript 
Groq API (LLaMA-3 8B Versatile)
CSS 


⚙️ Installation (Developer Mode)

1. Clone the repository
git clone https://github.com/your-username/casl-extension.git
2. Open Chrome and go to:
chrome://extensions
3. Enable Developer mode
4. Click Load unpacked
5. Select the CASL project folder
6. Done 🎉

Dont forget to add your own groq api key and configure it.

🧪 How to Use

1. Open any regular webpage 
2. Highlight a word or phrase
3. Click the ✨ AI button
4. Read the contextual explanation instantly


🔮 Future Enhancements

💾 Save explanations to a personal knowledge log
🌐 Multi-language support

