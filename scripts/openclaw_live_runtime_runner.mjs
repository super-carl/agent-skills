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

const toolNames = [
  "agent_session",
  "people_search",
  "company_search",
  "jobs_search",
  "posts_search",
  "people_lookup_batch",
  "social_proximity_research",
  "project_action",
  "send_communication",
  "watch_signals",
];

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

Run the workflow now against the mock Super Carl MCP tools. Use direct search/project/communication tools for direct skills and \`watch_signals\` for hosted watch skills. Stop after the requested search, project grouping, draft, approved send, or watch/action setup is complete.
`.trim();
}

function buildExtraSystemPrompt() {
  return `
You are running inside the OpenClaw embedded agent runtime for a live stochastic Super Carl skill validation.

Use the available Super Carl MCP tools whenever the user request requires search, project grouping, outreach review, or hosted watching. Do not answer only in prose when a tool call is needed.

Contract:
- For direct skills, start with \`agent_session\` mode="start" and pass the returned \`agent_session_id\` to later search, project, and communication tools.
- Direct skills should bind work to a project through \`agent_session\` mode="switch_project" when a project is named, or through \`project_action\` mode="add_targets" with \`agent_session_id\` when grouping selected targets.
- If the user refers to the current or selected Super Carl project without giving an id, use the current \`agent_session_id\` with \`project_action\` rather than asking for a project id.
- After adding targets, the normal next action is a project-bound draft: use \`project_action\` mode="generate_messages" for grouped outreach, or project-bound \`send_communication\` mode="precheck" -> mode="history" -> mode="draft" for one exact target.
- \`send_communication\` mode="send" is allowed only when the user explicitly approved the exact target, channel, and message; pass \`user_confirmed: true\` and project/target identifiers.
- Even for an explicitly approved send, call project-bound \`send_communication\` mode="precheck" and mode="history" before mode="send" unless those exact checks already happened in the same trace.
- In this validation harness, a user request that says add, group, generate, draft, save, or send is explicit approval for that requested mutating step. Pass \`user_confirmed: true\` for requested project mutations, but still do not send unless the prompt says send or approved.
- \`project_action\` mode="update_message" is mutating; include \`user_confirmed: true\` when saving the requested draft.
- For job and post searches that ask for people, pass \`with_people: true\`.
- For watch skills, create or update a durable watch with \`watch_signals\` mode="create" or mode="update" when the skill configures a watch.
- For watch hits, use \`hits\` and then \`evidence\` before \`promote_hit\`; every \`evidence\` call must include a concrete \`signal_hit_id\` from a prior \`hits\` result.
- When creating or updating a watch that can lead to outreach or project actions, include \`action_policy.never_send_without_approval: true\`.
- If the active watch skill says the flow is delivery/status-only or says not to promote hits, do not call \`promote_hit\`.
- Preserve \`project_feed\` when enabling \`agent_webhook\`.
`.trim();
}

function objectSchema(properties, required = []) {
  return {
    type: "object",
    properties,
    required,
    additionalProperties: true,
  };
}

function buildToolDefinitions() {
  const stringArray = { type: "array", items: { type: "string" } };
  const objectArray = { type: "array", items: { type: "object", additionalProperties: true } };
  return [
    {
      name: "agent_session",
      description: "Mock Super Carl MCP tool to start, bind, switch project, check, or close an external agent session.",
      parameters: objectSchema({
        mode: { type: "string", enum: ["start", "bind", "list", "switch_project", "status", "close"] },
        agent_name: { type: "string" },
        agent_session_id: { type: "string" },
        project_id: { type: "string" },
        search: { type: "string" },
        external_thread_ref: { type: "string" },
      }, ["mode"]),
    },
    {
      name: "people_search",
      description: "Mock Super Carl people search for immediate ICP, candidate, hiring-manager, warm-path, and shortlist discovery.",
      parameters: objectSchema({
        agent_session_id: { type: "string" },
        query: { type: "string" },
        role_intent: { type: "string" },
        company_ids: stringArray,
        post_ids: stringArray,
        include_social_proximity: { type: "boolean" },
        evidence_required: { type: "boolean" },
        limit: { type: "integer" },
        source_tool: { type: "string" },
      }),
    },
    {
      name: "company_search",
      description: "Mock Super Carl company search.",
      parameters: objectSchema({ agent_session_id: { type: "string" }, query: { type: "string" }, limit: { type: "integer" } }),
    },
    {
      name: "jobs_search",
      description: "Mock Super Carl jobs search. Use with with_people=true for hiring managers, recruiters, or warm paths.",
      parameters: objectSchema({
        agent_session_id: { type: "string" },
        query: { type: "string" },
        with_people: { type: "boolean" },
        fit_profile: { type: "string" },
        exclude_functions: stringArray,
        evidence_required: { type: "boolean" },
        limit: { type: "integer" },
      }),
    },
    {
      name: "posts_search",
      description: "Mock Super Carl post/activity search. Use with with_people=true to pivot engagement into targets.",
      parameters: objectSchema({
        agent_session_id: { type: "string" },
        query: { type: "string" },
        with_people: { type: "boolean" },
        role_intent: { type: "string" },
        evidence_required: { type: "boolean" },
        limit: { type: "integer" },
      }),
    },
    {
      name: "people_lookup_batch",
      description: "Mock Super Carl people lookup batch for outreach context and intro paths.",
      parameters: objectSchema({
        agent_session_id: { type: "string" },
        profiles: objectArray,
        relationship_detail: { type: "string" },
      }),
    },
    {
      name: "social_proximity_research",
      description: "Mock Super Carl social proximity research.",
      parameters: objectSchema({
        agent_session_id: { type: "string" },
        target_user_id: { type: "string" },
        status_only: { type: "boolean" },
      }),
    },
    {
      name: "project_action",
      description: "Mock Super Carl project tool for grouping targets, generating messages, saving drafts, readiness, and activation.",
      parameters: objectSchema({
        mode: {
          type: "string",
          enum: [
            "list",
            "status",
            "targets",
            "recipient_emails",
            "metrics",
            "send_readiness",
            "add_targets",
            "remove_targets",
            "retry_failed_linkedin_sends",
            "rename",
            "update_engagement_mode",
            "update_templates",
            "generate_templates",
            "generate_messages",
            "update_message",
            "activate",
          ],
        },
        agent_session_id: { type: "string" },
        project_id: { type: "string" },
        project_target_id: { type: "string" },
        target_user_ids: stringArray,
        target_user_id: { type: "string" },
        target_ids: stringArray,
        engagement_mode: { type: "string", enum: ["quick_text", "schedule_live"] },
        outreach_intent_type: { type: "string" },
        outreach_intent_description: { type: "string" },
        message: { type: "string" },
        review_action: { type: "string" },
        user_confirmed: { type: "boolean" },
        include_evidence: { type: "boolean" },
      }, ["mode"]),
    },
    {
      name: "send_communication",
      description: "Mock Super Carl communication tool. Normally project-bound. Use precheck -> history -> draft; use send only after explicit approval.",
      parameters: objectSchema({
        mode: { type: "string", enum: ["precheck", "history", "draft", "send", "status", "cancel"] },
        agent_session_id: { type: "string" },
        project_id: { type: "string" },
        project_target_id: { type: "string" },
        target_user_id: { type: "string" },
        channels: stringArray,
        requested_channels: stringArray,
        channel: { type: "string" },
        message: { type: "string" },
        subject: { type: "string" },
        history_fresh: { type: "boolean" },
        user_confirmed: { type: "boolean" },
        approval_required: { type: "boolean" },
      }, ["mode"]),
    },
    {
      name: "watch_signals",
      description: "Mock Super Carl MCP tool for hosted Scan My Network watch projects.",
      parameters: objectSchema({
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
        sources: objectArray,
        watch_prompt: { type: "string" },
        signal_types: stringArray,
        delivery_channels: stringArray,
        callback_policy: { type: "object", additionalProperties: true },
        freshness_policy: { type: "object", additionalProperties: true },
        action_policy: { type: "object", additionalProperties: true },
        estimated_preview_searches_per_run: { type: "integer" },
        signal_hit_id: { type: "string" },
        draft_message: { type: "boolean" },
        actions: stringArray,
      }, ["mode"]),
    },
  ];
}

function pluginSource() {
  return `
const fs = require("node:fs");

const scenario = process.env.SUPER_CARL_LIVE_SCENARIO;
const runtime = "openclaw";
const traceFile = process.env.SUPER_CARL_LIVE_TRACE_FILE;
const suffix = scenario + "_" + runtime.replace(/-/g, "_");
const agentSessionId = "session_" + suffix;
const projectId = "project_" + suffix;
const watchConfigId = "watch_" + suffix;
const hitId = "hit_" + suffix + "_1";
const personIds = [1, 2, 3, 4].map((index) => "person_" + suffix + "_" + index);
const projectTargetIds = [1, 2, 3, 4].map((index) => "target_" + suffix + "_" + index);
const jobId = "job_" + suffix + "_1";
const companyId = "company_" + suffix + "_1";
const postId = "post_" + suffix + "_1";
const toolDefinitions = ${JSON.stringify(buildToolDefinitions())};

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

function responseFor(tool, request) {
  const req = normalizeArgs(request);
  if (tool === "watch_signals" && !req.project_id) {
    req.project_id = projectId;
  }
  appendTrace({ tool, ...req });

  if (tool === "agent_session") {
    if (req.mode === "start") return { success: true, agent_session_id: agentSessionId, session_binding: { status: "started", agent_session_id: agentSessionId } };
    if (["bind", "switch_project", "status"].includes(req.mode)) return { success: true, agent_session_id: req.agent_session_id || agentSessionId, project_id: req.project_id || projectId, session_binding: { status: "bound", agent_session_id: req.agent_session_id || agentSessionId, project_id: req.project_id || projectId } };
    return { success: true, agent_session_id: agentSessionId };
  }
  if (tool === "people_search") {
    const query = String(req.query || "").toLowerCase();
    const headline = query.includes("revops") || query.includes("vp sales") || req.role_intent === "sales" ? "VP Sales at ExampleCo" : "VP Engineering at ExampleCo";
    return { search_id: "people_search_" + scenario, users: personIds.slice(0, 3).map((id, index) => ({ id, name: "Candidate " + (index + 1), headline, match_reasons: ["role fit", "company fit", "social proximity"], evidence_citations: [{ kind: "profile", snippet: "Current role and company match the query." }], relationship: { social_proximity_score: 0.78 } })), next_actions: [{ id: "people_search.run_review", tool: "people_search" }, { id: "social_proximity_research.start", tool: "social_proximity_research" }] };
  }
  if (tool === "company_search") {
    return { search_id: "company_search_" + scenario, companies: [{ id: companyId, name: "ExampleCo", fit: "AI infrastructure" }], next_actions: [{ id: "people_search.bind_company", tool: "people_search" }] };
  }
  if (tool === "jobs_search") {
    const payload = { search_id: "jobs_search_" + scenario, jobs: [{ id: jobId, title: "VP Engineering", company_id: companyId, company_name: "ExampleCo", fit_reasons: ["engineering leadership", "AI infrastructure", "startup stage"], evidence_citations: [{ kind: "job", snippet: "Role requirements match profile." }] }], next_actions: [{ id: "people_search.bind_job_company", tool: "people_search" }] };
    if (req.with_people) payload.people_by_company = { [companyId]: [{ id: personIds[0], name: "Engineering Leader", path: "hiring manager or leadership path" }] };
    return payload;
  }
  if (tool === "posts_search") {
    const payload = { search_id: "posts_search_" + scenario, posts: [{ id: postId, url: "https://example.com/post", snippet: "Competitor discussion about GTM monitoring.", engagement: [{ person_id: personIds[0], type: "comment" }] }], people_search_binding: { source_tool: "posts_search", post_ids: [postId] }, next_actions: [{ id: "people_search.from_posts", tool: "people_search" }] };
    if (req.with_people) payload.people = [{ id: personIds[0], name: "Engaged ICP" }];
    return payload;
  }
  if (tool === "people_lookup_batch") {
    return { profiles: [{ id: personIds[0], relationship: { social_map: { entries: [{ path_type: "confirmed_mutual", connector: "Known Connector", evidence: "Shared prior employer" }] } } }] };
  }
  if (tool === "social_proximity_research") {
    return { target_user_id: req.target_user_id || personIds[0], status: "completed", paths: [{ connector_user_id: personIds[2], strength: "warm" }] };
  }
  if (tool === "project_action") {
    if (req.mode === "add_targets") return { project_id: req.project_id || projectId, current_session_project_id: projectId, added_count: (req.target_user_ids || (req.target_user_id ? [req.target_user_id] : [])).length, targets: projectTargetIds.slice(0, 2).map((project_target_id, index) => ({ project_target_id, target_user_id: personIds[index] })) };
    if (req.mode === "targets") return { project_id: req.project_id || projectId, targets: [{ project_target_id: projectTargetIds[0], target_user_id: personIds[0], outreach_status: "pending", reviewed_message: "The exact reviewed message the user approved.", message: "The exact reviewed message the user approved.", channel: "linkedin_send_message", evidence: [{ kind: "profile", snippet: "Evidence supports outreach." }] }] };
    if (req.mode === "generate_messages") return { project_id: req.project_id || projectId, generated_count: 2, drafts: [{ project_target_id: projectTargetIds[0], message: "Personalized draft using cited evidence." }] };
    if (req.mode === "update_message") return { project_id: req.project_id || projectId, project_target_id: req.project_target_id || projectTargetIds[0], saved: true, review_action: req.review_action || "save" };
    if (req.mode === "send_readiness") return { project_id: req.project_id || projectId, ready_count: 2, not_previewed_count: 0 };
    return { project_id: req.project_id || projectId, status: "ok" };
  }
  if (tool === "send_communication") {
    if (req.mode === "precheck") return { target_user_id: req.target_user_id || personIds[0], channels: [{ channel: "gmail_send", available: true }, { channel: "linkedin_send_message", available: true }, { channel: "supercarl_referral_request", available: true }] };
    if (req.mode === "history") return { target_user_id: req.target_user_id || personIds[0], entries: [], next_actions: [{ id: "people_lookup_batch.outreach_context", tool: "people_lookup_batch", args: { relationship_detail: "intro_paths" } }] };
    if (req.mode === "draft") return { target_user_id: req.target_user_id || personIds[0], draft: { channel: req.channel || "linkedin_send_message", message: req.message || "" }, sent: false };
    if (req.mode === "send") return { status: "sent", project_id: req.project_id || projectId, project_target_id: req.project_target_id || projectTargetIds[0] };
    return { status: "ok" };
  }
  if (tool === "watch_signals") {
    if (req.mode === "role_packs") return { role_packs: ["gtm", "founder", "sales", "job_seeker", "recruiter", "networking"] };
    if (req.mode === "create" || req.mode === "update") return { project_id: req.project_id, watch_config_id: req.watch_config_id || watchConfigId, status: "active", delivery_channels: req.delivery_channels || ["project_feed"], credits: { estimated_preview_searches_per_run: req.estimated_preview_searches_per_run || 3 } };
    if (req.mode === "run_now") return { project_id: req.project_id, watch_config_id: req.watch_config_id || watchConfigId, run_id: "run_" + suffix, status: "completed" };
    if (req.mode === "hits") return { hits: [{ signal_hit_id: hitId, score: 0.91, match_reasons: ["ICP fit", "recent signal", "social proximity path available"], evidence_citations: [{ kind: "post_or_profile", title: "Recent relevant signal", url: "https://example.com/evidence" }] }] };
    if (req.mode === "evidence") return { signal_hit_id: req.signal_hit_id || hitId, citations: [{ kind: "profile_or_post", snippet: "Inspectable evidence supporting the signal.", url: "https://example.com/evidence" }, { kind: "social_proximity", snippet: "Warm path through a known relationship." }], recipient_context: { receptivity: "medium_high", recommended_opener: "Lead with the cited evidence and useful context." } };
    if (req.mode === "promote_hit") return { signal_hit_id: req.signal_hit_id || hitId, project_action: { routed: true, approval_required: true, draft_message: Boolean(req.draft_message) } };
    if (req.mode === "delivery_status") return { project_id: req.project_id, channels: [{ channel: "project_feed", status: "delivered", event_type: "digest_ready" }, { channel: "agent_webhook", status: "delivered", event_type: "signal_hit" }] };
    return { project_id: req.project_id, status: "ok" };
  }
  throw new Error("unsupported tool: " + tool);
}

module.exports = {
  id: "super-carl-live-test",
  name: "Super Carl Live Test",
  description: "Mock Super Carl MCP surfaces for live agent skill validation.",
  configSchema: { type: "object", additionalProperties: false, properties: {} },
  register(api) {
    for (const definition of toolDefinitions) {
      api.registerTool({
        name: definition.name,
        label: definition.name,
        description: definition.description,
        parameters: definition.parameters,
        async execute(_id, params) {
          return { content: [{ type: "text", text: JSON.stringify(responseFor(definition.name, params)) }] };
        },
      });
    }
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
        description: "Mock Super Carl MCP surfaces for live agent skill validation.",
        contracts: { tools: toolNames },
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
      allow: toolNames,
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
    toolsAllow: toolNames,
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
