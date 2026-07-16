(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.SafeOpsLogic = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function formatRiskScore(score) {
    if (score === null || score === undefined || score === "") {
      return "-";
    }
    return `${score}/100`;
  }

  function normalizeSessionId(value) {
    return String(value || "")
      .replace(/[^A-Za-z0-9_-]/g, "")
      .slice(0, 64);
  }

  function sortTools(tools) {
    return [...(Array.isArray(tools) ? tools : [])].sort((left, right) => {
      return `${left.category || ""}.${left.name || ""}`
        .localeCompare(`${right.category || ""}.${right.name || ""}`);
    });
  }

  function buildAuditQuery(filters) {
    const params = new URLSearchParams();
    const source = String(filters && filters.source || "");
    const risk = String(filters && filters.risk || "");
    const tool = String(filters && filters.tool || "").trim();
    if (source) {
      params.set("source", source);
    }
    if (risk) {
      params.set("risk", risk);
    }
    if (tool) {
      params.set("tool", tool);
    }
    return params.toString();
  }

  function buildAgentDetail(result) {
    return {
      tool: result.tool,
      risk: result.risk,
      riskScore: result.risk_score,
      requiresConfirmation: Boolean(result.requires_confirmation),
      decisionSummary: result.decision_summary,
      data: result.data,
      decisionTrace: result.decision_trace || result.reasoning_chain,
      pendingActionId: result.pending_action_id,
    };
  }

  async function requestJson(fetcher, url, options) {
    const response = await fetcher(url, {...(options || {}), credentials: "same-origin"});
    const payload = await response.json();
    if (!response.ok && response.status !== 202) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  return Object.freeze({
    buildAgentDetail,
    buildAuditQuery,
    formatRiskScore,
    normalizeSessionId,
    requestJson,
    sortTools,
  });
});
