# CASL — In-Browser Workspace Overlay (Chrome Extension V3)

The in-browser workspace overlay allows financial analysts and legal associates to conduct due diligence directly within their active reading surface without tab context-switching.

---

## 1. Extension Component Breakdown

```
CASL Chrome Extension (Manifest V3)
├── manifest.json       <-- Permissions (storage), service worker registration, options page
├── background.js       <-- Service worker proxy, dynamic gateway dispatch, 402 handler
├── content.js          <-- DOM listener, selection debouncer, viewport tooltip renderer
├── styles.css          <-- Floating HUD styling, citation pills, animation transitions
├── options.html        <-- Enterprise settings page (Gateway URL, Tenant ID, Auth)
└── options.js          <-- Storage synchronization logic
```

---

## 2. Selection Debounce & Viewport Anchoring (`content.js`)

Highlighting text in 150-page regulatory filings presents two major challenges:
1. **Vertical Coordinate Drift**:
   - If tooltips are positioned using `window.scrollY + 120px`, highlighting text at line 5,000 will render the tooltip thousands of pixels above the active screen.
   - `content.js` captures `lastSelectionRect = range.getBoundingClientRect()` and dynamically calculates top/left offsets relative to the viewport.
2. **Rapid Highlighting Race Conditions**:
   - Rapidly selecting word A and then word B can cause asynchronous API responses to overwrite or prematurely close active tooltips.
   - `content.js` increments `currentSelectionSeq++` and checks sequence IDs on arrival, discarding stale responses.

---

## 3. Quota Exhaustion & HUD Feedback (`background.js`)

When an analyst's firm reaches its monthly research quota:
1. The backend returns `HTTP 402 Payment Required` with `detail: "Monthly credit quota exceeded..."`.
2. `background.js` intercepts status `402` and converts it into a structured notification object.
3. `content.js` renders a clean alert in the HUD:
   ```text
   ⚠️ Monthly credit quota exceeded. 
   Upgrade your workspace plan to resume research.
   Billing hard cap enforced. Credit consumption halted.
   ```
   This provides immediate clarity to the analyst rather than failing silently.

---

## 4. Enterprise Options HUD (`options.html`)

The extension provides an Options page accessible via `chrome://extensions`:
- **Gateway Ingress URL**: Default `http://localhost:8000`, configurable to corporate HTTPS endpoints (e.g. `https://api.yourfirm.com`).
- **Tenant ID**: Configurable workspace partition (`default`, `kirkland-ellis`, `alpha-fund`).
- **Enterprise Bearer / API Key**: Injects corporate authentication tokens.
- **Personal Groq Key (Optional)**: Allows individual developers to supply their own key for local offline fallback.

