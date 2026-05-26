---
name: super-carl-agent-webhook-digests
description: Configure Super Carl agent_webhook delivery for hosted watch updates while preserving project feed, app push, email digest, evidence inspection, and polling fallbacks.
license: MIT
metadata:
  super_carl:
    role_intents: [general]
    primary_tool: watch_signals
---

# Super Carl Agent Webhook Digests

Use this when an agent host can receive durable callback or trackback events and the user wants watch updates delivered back to that agent environment.

## Flow

1. Use the Super Carl MCP tool `watch_signals`; confirm the webhook/callback endpoint, callback id, and whether it routes for one user or multiple delegated users.
2. Keep `project_feed` enabled even when `agent_webhook` is configured.
3. Use `delivery_channels: ["project_feed", "agent_webhook"]` plus app/email channels if desired.
4. Add `callback_policy` with `callback_id`, `mcp_connection_id`, `event_types`, and optional team/delegate routing metadata.
5. Use `delivery_status` immediately after the update to verify callback delivery. This skill is about notification routing, not outreach or hit promotion.
6. Fallback to `status`, `hits`, and `evidence` polling only if webhook delivery fails or the user explicitly asks to inspect the underlying signal content. If using `evidence`, first call `hits` and pass the returned `signal_hit_id`; never call `evidence` without a concrete `signal_hit_id`.
7. Do not call `promote_hit` from this skill; webhook setup must not create drafts or project actions unless the user switches to an outreach/review skill.

## Example Update

```json
{
  "mode": "update",
  "project_id": "PROJECT_ID",
  "watch_config_id": "WATCH_CONFIG_ID",
  "delivery_channels": ["project_feed", "agent_webhook", "email_digest"],
  "callback_policy": {
    "callback_id": "openclaw-prod",
    "mcp_connection_id": "mcp_connection_123",
    "event_types": ["signal_hit", "digest_ready", "draft_ready"],
    "delegate_routing": "allow_team_sub_users"
  }
}
```

## Delivery Interpretation

`agent_webhook` is a notification channel, not the scheduler of record. Super Carl still owns the watch, run timing, dedupe, credit pause/resume, evidence storage, and approval-gated project actions.

For this skill, a successful run usually ends after `delivery_status`. If `delivery_status` confirms `agent_webhook` and `project_feed`, summarize the routing state and stop.

## Guardrails

- Do not assume a callback woke the agent unless `delivery_status` confirms it.
- Do not drop project feed or email/app fallback unless the user explicitly requests it.
- Do not call `promote_hit` or request `draft_message` while configuring callbacks.
- Do not call `evidence` without a `signal_hit_id` returned from `hits`.
- Do not send outreach based on webhook payloads alone; fetch `evidence` and keep approval in the project.
