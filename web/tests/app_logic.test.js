const test = require("node:test");
const assert = require("node:assert/strict");

const logic = require("../app_logic.js");


test("formatRiskScore preserves zero and formats missing values", () => {
  assert.equal(logic.formatRiskScore(0), "0/100");
  assert.equal(logic.formatRiskScore(87), "87/100");
  assert.equal(logic.formatRiskScore(null), "-");
  assert.equal(logic.formatRiskScore(""), "-");
});

test("normalizeSessionId removes unsupported characters and enforces the server limit", () => {
  assert.equal(logic.normalizeSessionId("abc; rm -rf /_OK"), "abcrm-rf_OK");
  assert.equal(logic.normalizeSessionId("x".repeat(80)).length, 64);
});

test("sortTools is deterministic without mutating API data", () => {
  const tools = [
    {category: "system", name: "system.info"},
    {category: "diagnostics", name: "diagnostics.disk"},
  ];
  const sorted = logic.sortTools(tools);

  assert.deepEqual(sorted.map((item) => item.category), ["diagnostics", "system"]);
  assert.equal(tools[0].category, "system");
});

test("buildAuditQuery trims and URL-encodes user filters", () => {
  assert.equal(
    logic.buildAuditQuery({source: "web", risk: "HIGH", tool: " service.status "}),
    "source=web&risk=HIGH&tool=service.status",
  );
  assert.equal(logic.buildAuditQuery({source: "", risk: "", tool: "  "}), "");
});

test("buildAgentDetail supports the reasoning_chain compatibility field", () => {
  const chain = [{step: 1, stage: "intent"}];
  const detail = logic.buildAgentDetail({
    tool: "system.info",
    risk_score: 5,
    reasoning_chain: chain,
    requires_confirmation: 0,
  });

  assert.equal(detail.tool, "system.info");
  assert.equal(detail.riskScore, 5);
  assert.equal(detail.requiresConfirmation, false);
  assert.equal(detail.decisionTrace, chain);
});

test("requestJson always uses same-origin credentials and accepts 202 workflows", async () => {
  let request;
  const payload = await logic.requestJson(async (url, options) => {
    request = {url, options};
    return {ok: false, status: 202, json: async () => ({ok: false, pending: true})};
  }, "/api/agent", {method: "POST", credentials: "omit"});

  assert.equal(request.url, "/api/agent");
  assert.equal(request.options.credentials, "same-origin");
  assert.equal(payload.pending, true);
});

test("requestJson exposes API errors to the interface", async () => {
  await assert.rejects(
    logic.requestJson(
      async () => ({ok: false, status: 401, json: async () => ({error: "unauthorized"})}),
      "/api/tools",
    ),
    /unauthorized/,
  );
});
