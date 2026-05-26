#!/usr/bin/env node
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const resultFile = requireEnv("SUPER_CARL_LIVE_RESULT_FILE");
const model = process.env.SUPER_CARL_LIVE_MODEL || "gpt-4.1-mini";
const scenario = requireEnv("SUPER_CARL_LIVE_SCENARIO");
const skill = requireEnv("SUPER_CARL_LIVE_SKILL");
const userPrompt = requireEnv("SUPER_CARL_LIVE_PROMPT");
const skillText = requireEnv("SUPER_CARL_LIVE_SKILL_TEXT");
const temperature = Number(process.env.SUPER_CARL_LIVE_TEMPERATURE || "0.7");
const openaiApiKey = requireEnv("OPENAI_API_KEY");
const openclawRoot = process.cwd();

function requireEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function normalizeArgs(args) {
  if (typeof args === "string") {
    try {
      return JSON.parse(args);
    } catch {
      return { mode: "status", raw: args };
    }
  }
  if (!args || typeof args !== "object") {
    return { mode: "status", raw: args };
  }
  if (!args.mode && args.request && typeof args.request === "object") {
    return { ...args.request };
  }
  return { ...args };
}

function buildPrompt() {
  return `
Load and follow this Super Carl skill:

<skill>
${skillText}
</skill>

User request:
${userPrompt}

Run the workflow now against the mock \`watch_signals\` MCP tool. If the workflow asks for a message, follow-up, intro request, or reviewed next action, call \`promote_hit\` after \`evidence\` with \`draft_message: true\`; this only queues a user-reviewable draft and does not send outreach. Stop after the watch/action setup and evidence-backed review are complete.
`.trim();
}

function buildExtraSystemPrompt() {
  return `
You are running inside the OpenClaw embedded agent runtime for a live stochastic Super Carl skill validation.

Use the \`watch_signals\` MCP tool whenever the user request involves configuring, running, inspecting, or delivering a Scan My Network watch. Do not answer only in prose when a tool call is needed.

Contract:
- Create or update a durable watch with \`mode: "create"\` or \`mode: "update"\` when the skill configures a watch.
- Use \`project_id\` when one is available.
- Use \`hits\` and then \`evidence\` before \`promote_hit\`.
- Every \`evidence\` call must include a concrete \`signal_hit_id\` from a prior \`hits\` result.
- When creating or updating a watch that can lead to outreach or project actions, include \`action_policy.never_send_without_approval: true\`.
- Never send outreach directly. \`promote_hit\` is not a send action; use it to prepare a reviewable project action or draft whenever the user asked for follow-up, outreach prep, intro prep, or next-action review.
- If the active skill says the flow is delivery/status-only or says not to promote hits, do not call \`promote_hit\`.
- Preserve \`project_feed\` when enabling \`agent_webhook\`.
- Carry role intent, source kinds, signal types, freshness policy, callback policy, and approval policy exactly when the skill calls for them.
`.trim();
}

function buildWatchSignalsParameters() {
  return {
    type: "object",
    properties: {
      mode: {
        type: "string",
        enum: [
          "role_packs",
          "create",
          "update",
          "run_now",
          "hits",
          "evidence",
          "promote_hit",
          "delivery_status",
          "status",
          "pause",
          "resume",
          "dismiss_hit",
          "snooze_hit",
        ],
      },
      project_id: { type: "string" },
      watch_config_id: { type: "string" },
      title: { type: "string" },
      role_intent: { type: "string" },
      source_kind: { type: "string" },
      sources: {
        type: "array",
        items: { type: "object", additionalProperties: true },
      },
      watch_prompt: { type: "string" },
      signal_types: { type: "array", items: { type: "string" } },
      delivery_channels: { type: "array", items: { type: "string" } },
      callback_policy: { type: "object", additionalProperties: true },
      freshness_policy: { type: "object", additionalProperties: true },
      action_policy: { type: "object", additionalProperties: true },
      estimated_preview_searches_per_run: { type: "integer" },
      signal_hit_id: { type: "string" },
      draft_message: { type: "boolean" },
      actions: { type: "array", items: { type: "string" } },
    },
    required: ["mode"],
    additionalProperties: true,
  };
}

function pluginSource() {
  return `
const fs = require("node:fs");

const scenario = process.env.SUPER_CARL_LIVE_SCENARIO;
const runtime = "openclaw";
const traceFile = process.env.SUPER_CARL_LIVE_TRACE_FILE;
const projectId = "project_" + scenario + "_" + runtime.replace(/-/g, "_");
const watchConfigId = "watch_" + scenario + "_" + runtime.replace(/-/g, "_");
const hitId = "hit_" + scenario + "_" + runtime.replace(/-/g, "_") + "_1";

function normalizeArgs(args) {
  if (typeof args === "string") {
    try {
      return JSON.parse(args);
    } catch {
      return { mode: "status", raw: args };
    }
  }
  if (!args || typeof args !== "object") {
    return { mode: "status", raw: args };
  }
  if (!args.mode && args.request && typeof args.request === "object") {
    return { ...args.request };
  }
  return { ...args };
}

function appendTrace(call) {
  fs.appendFileSync(traceFile, JSON.stringify(call) + "\\n", "utf8");
}

function responseFor(request) {
  const req = normalizeArgs(request);
  if (!req.project_id) {
    req.project_id = projectId;
  }
  const mode = req.mode;
  if (!mode) {
    throw new Error("watch_signals call missing mode");
  }
  appendTrace(req);

  if (mode === "role_packs") {
    return { role_packs: ["gtm", "founder", "sales", "job_seeker", "recruiter", "networking"] };
  }
  if (mode === "create" || mode === "update") {
    return {
      project_id: req.project_id,
      watch_config_id: req.watch_config_id || watchConfigId,
      status: "active",
      delivery_channels: req.delivery_channels || ["project_feed"],
      credits: { estimated_preview_searches_per_run: req.estimated_preview_searches_per_run || 3 },
    };
  }
  if (mode === "run_now") {
    return {
      project_id: req.project_id,
      watch_config_id: req.watch_config_id || watchConfigId,
      run_id: "run_" + scenario + "_" + runtime.replace(/-/g, "_"),
      status: "completed",
    };
  }
  if (mode === "hits") {
    return {
      hits: [
        {
          signal_hit_id: hitId,
          score: 0.91,
          match_reasons: ["ICP fit", "recent signal", "social proximity path available"],
          evidence_citations: [
            { kind: "post_or_profile", title: "Recent relevant signal", url: "https://example.com/evidence" },
          ],
        },
      ],
    };
  }
  if (mode === "evidence") {
    return {
      signal_hit_id: req.signal_hit_id || hitId,
      citations: [
        { kind: "profile_or_post", snippet: "Inspectable evidence supporting the signal.", url: "https://example.com/evidence" },
        { kind: "social_proximity", snippet: "Warm path through a known relationship." },
      ],
      recipient_context: {
        receptivity: "medium_high",
        recommended_opener: "Lead with the cited evidence and useful context.",
      },
    };
  }
  if (mode === "promote_hit") {
    return {
      signal_hit_id: req.signal_hit_id || hitId,
      project_action: {
        routed: true,
        approval_required: true,
        draft_message: Boolean(req.draft_message),
      },
    };
  }
  if (mode === "delivery_status") {
    return {
      project_id: req.project_id,
      channels: [
        { channel: "project_feed", status: "delivered", event_type: "digest_ready" },
        { channel: "agent_webhook", status: "delivered", event_type: "signal_hit" },
      ],
    };
  }
  if (["status", "pause", "resume", "dismiss_hit", "snooze_hit"].includes(mode)) {
    return { project_id: req.project_id, status: "ok" };
  }
  throw new Error("unsupported watch_signals mode: " + mode);
}

module.exports = {
  id: "super-carl-live-test",
  name: "Super Carl Live Test",
  description: "Mock Super Carl watch_signals MCP surface for live agent skill validation.",
  configSchema: { type: "object", additionalProperties: false, properties: {} },
  register(api) {
    api.registerTool({
      name: "watch_signals",
      label: "watch_signals",
      description: "Mock Super Carl MCP tool for Scan My Network watch projects.",
      parameters: ${JSON.stringify(buildWatchSignalsParameters())},
      async execute(_id, params) {
        return {
          content: [{ type: "text", text: JSON.stringify(responseFor(params)) }],
        };
      },
    });
  },
};
`;
}

async function writePlugin(pluginDir) {
  await fsp.mkdir(pluginDir, { recursive: true });
  await fsp.writeFile(
    path.join(pluginDir, "openclaw.plugin.json"),
    JSON.stringify(
      {
        id: "super-carl-live-test",
        name: "Super Carl Live Test",
        description: "Mock Super Carl watch_signals MCP surface for live agent skill validation.",
        contracts: { tools: ["watch_signals"] },
        activation: { onStartup: true },
        configSchema: { type: "object", additionalProperties: false, properties: {} },
      },
      null,
      2,
    ),
  );
  await fsp.writeFile(path.join(pluginDir, "index.js"), pluginSource());
}

function buildConfig(pluginDir) {
  return {
    models: {
      providers: {
        openai: {
          baseUrl: "https://api.openai.com/v1",
          apiKey: openaiApiKey,
          auth: "api-key",
          api: model.startsWith("gpt-5") ? "openai-responses" : "openai-completions",
          contextWindow: 128000,
          maxTokens: 4096,
          models: [
            {
              id: model,
              contextWindow: 128000,
              maxTokens: 4096,
              api: model.startsWith("gpt-5") ? "openai-responses" : "openai-completions",
              params: Number.isFinite(temperature) ? { temperature } : {},
            },
          ],
        },
      },
    },
    plugins: {
      enabled: true,
      allow: ["super-carl-live-test"],
      load: { paths: [pluginDir] },
      entries: { "super-carl-live-test": { enabled: true } },
    },
    tools: {
      allow: ["watch_signals"],
      deny: [],
    },
  };
}

const tmpRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "super-carl-openclaw-live-"));
const workspaceDir = path.join(tmpRoot, "workspace");
const agentDir = path.join(tmpRoot, "agent");
const pluginDir = path.join(tmpRoot, "plugin");
const traceFile = path.join(tmpRoot, "trace.jsonl");
const sessionFile = path.join(tmpRoot, "session.json");
process.env.SUPER_CARL_LIVE_TRACE_FILE = traceFile;

try {
  await fsp.mkdir(workspaceDir, { recursive: true });
  await fsp.mkdir(agentDir, { recursive: true });
  await writePlugin(pluginDir);

  const { runEmbeddedPiAgent } = await import(
    pathToFileURL(path.join(openclawRoot, "src/agents/pi-embedded-runner/run.ts")).href
  );

  const started = Date.now();
  const result = await runEmbeddedPiAgent({
    sessionId: `super-carl-live-${scenario}`,
    sessionKey: `super-carl-live-${scenario}`,
    sessionFile,
    workspaceDir,
    agentDir,
    config: buildConfig(pluginDir),
    prompt: buildPrompt(),
    transcriptPrompt: userPrompt,
    extraSystemPrompt: buildExtraSystemPrompt(),
    provider: "openai",
    model,
    timeoutMs: 180000,
    runTimeoutOverrideMs: 180000,
    runId: `super-carl-live-${scenario}-${Date.now()}`,
    disableMessageTool: true,
    toolsAllow: ["watch_signals"],
    streamParams: Number.isFinite(temperature) ? { temperature } : undefined,
    trigger: "manual",
  });

  const calls = fs.existsSync(traceFile)
    ? fs
        .readFileSync(traceFile, "utf8")
        .split("\n")
        .filter(Boolean)
        .map((line) => normalizeArgs(JSON.parse(line)))
    : [];
  await fsp.writeFile(
    resultFile,
    JSON.stringify(
      {
        elapsed_ms: Date.now() - started,
        calls,
        payloads: result.payloads ?? [],
        meta: {
          stopReason: result.meta?.stopReason,
          livenessState: result.meta?.livenessState,
          finalAssistantVisibleText: result.meta?.finalAssistantVisibleText,
          finalAssistantRawText: result.meta?.finalAssistantRawText,
          pendingToolCalls: result.meta?.pendingToolCalls,
          error: result.meta?.error,
        },
      },
      null,
      2,
    ),
  );
} finally {
  await fsp.rm(tmpRoot, { recursive: true, force: true });
}
