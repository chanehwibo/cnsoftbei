const messages = document.querySelector("#messages");
const form = document.querySelector("#requestForm");
const input = document.querySelector("#requestInput");
const confirmInput = document.querySelector("#confirmInput");
const health = document.querySelector("#health");
const toolsEl = document.querySelector("#tools");
const auditEl = document.querySelector("#audit");
const lastTool = document.querySelector("#lastTool");
const lastRisk = document.querySelector("#lastRisk");
const confirmState = document.querySelector("#confirmState");
const toolCount = document.querySelector("#toolCount");

function addMessage(role, text, data, risk) {
  const item = document.createElement("div");
  item.className = `message ${role}${risk ? ` risk-${risk}` : ""}`;
  const title = document.createElement("strong");
  title.textContent = role === "user" ? "请求" : "响应";
  const body = document.createElement("div");
  body.textContent = text;
  item.append(title, body);
  if (data) {
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(data, null, 2);
    item.append(pre);
  }
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  return response.json();
}

async function sendRequest(text) {
  addMessage("user", text);
  const result = await requestJson("/api/agent", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({request: text, confirmed: confirmInput.checked}),
  });
  lastTool.textContent = result.tool || "-";
  lastRisk.textContent = result.risk || "-";
  confirmState.textContent = result.requires_confirmation ? "需要确认" : "无需确认";
  addMessage("agent", result.message || result.error || "无响应", result.data, result.risk);
  await loadAudit();
}

async function loadTools() {
  const result = await requestJson("/api/tools");
  const tools = result.tools || [];
  toolCount.textContent = tools.length;
  toolsEl.innerHTML = "";
  for (const tool of tools) {
    const item = document.createElement("div");
    item.className = "tool-item";
    item.innerHTML = `<strong>${tool.name}</strong><span class="tag ${tool.risk}">${tool.risk}</span><div>${tool.category}</div>`;
    toolsEl.append(item);
  }
}

async function loadAudit() {
  const result = await requestJson("/api/audit");
  const events = result.events || [];
  auditEl.innerHTML = "";
  for (const event of events.slice().reverse()) {
    const item = document.createElement("div");
    item.className = "audit-item";
    const risk = event.risk || "-";
    item.innerHTML = `<strong>${event.request || "-"}</strong><span class="tag ${risk}">${risk}</span><div>${event.tool || event.event_type || "-"}</div><div>${event.reason || "-"}</div>`;
    auditEl.append(item);
  }
}

async function loadHealth() {
  try {
    const result = await requestJson("/api/health");
    health.textContent = result.ok ? "已连接" : "连接异常";
  } catch {
    health.textContent = "连接失败";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) {
    return;
  }
  input.value = "";
  try {
    await sendRequest(text);
  } catch (error) {
    addMessage("agent", `请求失败：${error.message}`);
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    input.focus();
  });
});

document.querySelector("#refreshAudit").addEventListener("click", loadAudit);

loadHealth();
loadTools();
loadAudit();
addMessage("agent", "工作台已就绪");
