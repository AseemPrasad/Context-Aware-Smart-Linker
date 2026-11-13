document.addEventListener("DOMContentLoaded", async () => {
  const gatewayUrlInput = document.getElementById("gatewayUrl");
  const tenantIdInput = document.getElementById("tenantId");
  const apiKeyInput = document.getElementById("apiKey");
  const groqKeyInput = document.getElementById("groqKey");
  const saveBtn = document.getElementById("saveBtn");
  const statusMsg = document.getElementById("statusMsg");

  // Load existing settings
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    const data = await chrome.storage.local.get(["caslGatewayUrl", "caslTenantId", "caslApiKey", "caslUserGroqKey"]);
    if (data.caslGatewayUrl) gatewayUrlInput.value = data.caslGatewayUrl;
    if (data.caslTenantId) tenantIdInput.value = data.caslTenantId;
    if (data.caslApiKey) apiKeyInput.value = data.caslApiKey;
    if (data.caslUserGroqKey) groqKeyInput.value = data.caslUserGroqKey;
  }

  // Save settings
  saveBtn.addEventListener("click", async () => {
    const gatewayUrl = gatewayUrlInput.value.trim() || "http://localhost:8000";
    const tenantId = tenantIdInput.value.trim() || "default";
    const apiKey = apiKeyInput.value.trim();
    const groqKey = groqKeyInput.value.trim();

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      await chrome.storage.local.set({
        caslGatewayUrl: gatewayUrl,
        caslTenantId: tenantId,
        caslApiKey: apiKey,
        caslUserGroqKey: groqKey
      });
      statusMsg.style.display = "block";
      setTimeout(() => {
        statusMsg.style.display = "none";
      }, 3000);
    }
  });
});

