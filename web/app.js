const messages = document.querySelector("#messages");
const form = document.querySelector("#requestForm");
const input = document.querySelector("#requestInput");
const confirmInput = document.querySelector("#confirmInput");
const health = document.querySelector("#health");
const toolsEl = document.querySelector("#tools");
const auditEl = document.querySelector("#audit");
const lastTool = document.querySelector("#lastTool");
const lastRisk = document.querySelector("#lastRisk");
const lastRiskScore = document.querySelector("#lastRiskScore");
const lastDecision = document.querySelector("#lastDecision");
const confirmState = document.querySelector("#confirmState");
const toolCount = document.querySelector("#toolCount");

function formatRiskScore(score) {
  if (score === null || score === undefined || score === "") {
    return "-";
  }
  return `${score}/100`;
}

function createTag(text, className) {
  const tag = document.createElement("span");
  tag.className = `tag ${className || ""}`.trim();
  tag.textContent = text;
  return tag;
}

function addChip(container, label, value, className) {
  if (value === null || value === undefined || value === "") {
    return;
  }
  const chip = createTag(`${label}: ${value}`, className);
  container.append(chip);
}

function appendList(container, title, values) {
  if (!Array.isArray(values) || values.length === 0) {
    return;
  }
  const block = document.createElement("div");
  block.className = "result-list";
  const label = document.createElement("strong");
  label.textContent = title;
  const list = document.createElement("ul");
  for (const value of values) {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  }
  block.append(label, list);
  container.append(block);
}

function appendDiagnosis(container, diagnosis) {
  const panel = document.createElement("section");
  panel.className = "result-panel diagnosis-panel";

  const title = document.createElement("h3");
  title.textContent = "诊断报告";
  panel.append(title);

  const scenario = document.createElement("p");
  scenario.textContent = diagnosis.scenario || "未识别诊断场景";
  panel.append(scenario);

  if (diagnosis.symptom) {
    const symptom = document.createElement("p");
    symptom.textContent = diagnosis.symptom;
    panel.append(symptom);
  }

  appendList(panel, "可能原因", diagnosis.possible_causes);
  appendList(panel, "建议动作", diagnosis.recommended_actions);
  appendList(panel, "后续请求", diagnosis.suggested_followups);

  container.append(panel);
}

function appendDryRunPlan(container, plan) {
  const panel = document.createElement("section");
  panel.className = "result-panel dry-run-panel";

  const title = document.createElement("h3");
  title.textContent = "Dry-run 预案";
  panel.append(title);

  const target = document.createElement("p");
  const service = plan.target && plan.target.service ? plan.target.service : "未识别服务";
  target.textContent = `目标操作：${plan.action || "service.restart"}，服务：${service}`;
  panel.append(target);

  appendList(panel, "前置检查", plan.pre_checks);
  appendList(panel, "计划步骤", plan.planned_steps);
  appendList(panel, "风险控制", plan.risk_controls);

  if (plan.rollback_suggestion) {
    const rollback = document.createElement("p");
    rollback.className = "rollback";
    rollback.textContent = plan.rollback_suggestion;
    panel.append(rollback);
  }

  container.append(panel);
}

function appendStructuredData(item, data) {
  if (!data) {
    return;
  }

  let hasStructuredView = false;
  if (data.diagnosis) {
    appendDiagnosis(item, data.diagnosis);
    hasStructuredView = true;
  }
  if (data.dry_run_plan) {
    appendDryRunPlan(item, data.dry_run_plan);
    hasStructuredView = true;
  }

  const details = document.createElement("details");
  details.className = "raw-data";
  details.open = !hasStructuredView;
  const summary = document.createElement("summary");
  summary.textContent = "原始数据";
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(data, null, 2);
  details.append(summary, pre);
  item.append(details);
}

function addMessage(role, text, detail = {}) {
  const item = document.createElement("div");
  item.className = `message ${role}${detail.risk ? ` risk-${detail.risk}` : ""}`;

  const title = document.createElement("strong");
  title.textContent = role === "user" ? "请求" : "响应";
  item.append(title);

  const meta = document.createElement("div");
  meta.className = "message-meta";
  addChip(meta, "工具", detail.tool);
  addChip(meta, "风险", detail.risk, detail.risk);
  addChip(meta, "评分", formatRiskScore(detail.riskScore));
  if (detail.requiresConfirmation) {
    addChip(meta, "确认", "需要人工确认", "MEDIUM");
  }
  if (meta.children.length > 0) {
    item.append(meta);
  }

  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text;
  item.append(body);

  if (detail.decisionSummary) {
    const summary = document.createElement("div");
    summary.className = "decision-summary";
    summary.textContent = detail.decisionSummary;
    item.append(summary);
  }

  appendStructuredData(item, detail.data);
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok && response.status !== 202) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function updateStatus(result) {
  lastTool.textContent = result.tool || "-";
  lastRisk.textContent = result.risk || "-";
  lastRisk.className = result.risk ? `risk-text ${result.risk}` : "";
  lastRiskScore.textContent = formatRiskScore(result.risk_score);
  confirmState.textContent = result.requires_confirmation ? "需要确认" : "无需确认";
  lastDecision.textContent = result.decision_summary || "-";
}

async function sendRequest(text) {
  addMessage("user", text);
  const result = await requestJson("/api/agent", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({request: text, confirmed: confirmInput.checked}),
  });
  updateStatus(result);
  addMessage("agent", result.message || result.error || "无响应", {
    tool: result.tool,
    risk: result.risk,
    riskScore: result.risk_score,
    requiresConfirmation: result.requires_confirmation,
    decisionSummary: result.decision_summary,
    data: result.data,
  });
  await loadAudit();
}

async function loadTools() {
  const result = await requestJson("/api/tools");
  const tools = (result.tools || []).slice().sort((left, right) => {
    return `${left.category}.${left.name}`.localeCompare(`${right.category}.${right.name}`);
  });
  toolCount.textContent = tools.length;
  toolsEl.innerHTML = "";
  for (const tool of tools) {
    const item = document.createElement("div");
    item.className = `tool-item ${tool.category === "diagnostics" ? "diagnostic-tool" : ""}`;

    const name = document.createElement("strong");
    name.textContent = tool.name;
    const risk = createTag(tool.risk, tool.risk);
    const category = document.createElement("div");
    category.className = "muted";
    category.textContent = tool.category;
    const description = document.createElement("div");
    description.textContent = tool.description || "-";

    item.append(name, risk, category, description);
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

    const title = document.createElement("strong");
    title.textContent = event.request || "-";
    const risk = createTag(event.risk || "-", event.risk || "");
    const score = createTag(formatRiskScore(event.risk_score), "score");
    const tool = document.createElement("div");
    tool.className = "muted";
    tool.textContent = event.tool || event.event_type || "-";
    const reason = document.createElement("div");
    reason.textContent = event.reason || "-";

    item.append(title, risk, score, tool, reason);
    if (event.decision_summary) {
      const summary = document.createElement("div");
      summary.className = "audit-summary";
      summary.textContent = event.decision_summary;
      item.append(summary);
    }
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

function connectSSE() {
  let url = "/api/events";
  const meta = document.querySelector('meta[name="safeops-token"]');
  if (meta && meta.content) {
    url += "?token=" + encodeURIComponent(meta.content);
  }
  const source = new EventSource(url);
  source.onmessage = function () {
    loadAudit();
  };
  source.onerror = function () {
    source.close();
    setTimeout(connectSSE, 5000);
  };
}

loadHealth();
loadTools();
loadAudit();
connectSSE();
addMessage("agent", "工作台已就绪");