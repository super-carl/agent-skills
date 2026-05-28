---
name: super-carl-project-outreach-review
description: Prepare approval-gated Super Carl outreach from existing project targets by checking evidence, channel eligibility, history, and draft quality before any send.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, job_seeker, recruiter, investor, bd, networking]
    primary_tool: send_communication
---

# Super Carl Project Outreach Review

Use this when the user has Super Carl project targets or search results and wants grouped outreach review, personalized message generation, intro requests, follow-ups, or an explicitly approved one-target send. This is a direct MCP workflow for project-bound communication, not a hosted watch.

## Flow

1. Start or bind an `agent_session`; if the user names a project, call `agent_session` with `mode: "switch_project"` before loading targets. If the user refers to the current or selected project, use `agent_session_id` with `project_action` and do not ask for a project id.
2. Use `project_action` with `agent_session_id` to load the project, selected targets, evidence, and any review state.
3. If evidence is missing, call the relevant search tool first: `people_search`, `jobs_search`, `posts_search`, `company_search`, or `social_proximity_research`.
4. For grouped project outreach, prefer `project_action` with `mode: "generate_messages"` so Super Carl drafts personalized messages against saved project context for all selected targets. After adding targets, this is the normal next suggestion.
5. For an exact per-target draft, call `send_communication` with `mode: "precheck"` to verify allowed channels and policy constraints.
6. Call `send_communication` with `mode: "history"` before drafting, so the message respects prior conversations and follow-up timing.
7. When warm-path or prior-context evidence matters, follow the returned `people_lookup_batch` outreach-context action or call it directly with `relationship_detail: "intro_paths"`.
8. Call project-bound `send_communication` with `mode: "draft"` using the cited evidence, role intent, product context, and desired engagement mode.
9. Use `project_action` with `mode: "update_message"` when saving an exact reviewed-later draft on a project target.
10. After a draft is saved, the normal next suggestion is to send or schedule that reviewed message. Even if the user says the draft is already approved, call project-bound `send_communication` with `mode: "precheck"` and `mode: "history"` before `mode: "send"` unless those exact checks already happened in the current trace. Call `send` only when the user explicitly approves the exact target, channel, and message.

## Example Draft Flow

```json
{
  "mode": "targets",
  "project_id": "PROJECT_ID",
  "agent_session_id": "AGENT_SESSION_ID",
  "include_evidence": true,
  "status": "ready_for_review"
}
```

```json
{
  "mode": "generate_messages",
  "project_id": "PROJECT_ID",
  "agent_session_id": "AGENT_SESSION_ID",
  "outreach_intent_type": "finding_customers",
  "outreach_intent_description": "Share useful context tied to the cited evidence.",
  "user_confirmed": true
}
```

```json
{
  "mode": "precheck",
  "agent_session_id": "AGENT_SESSION_ID",
  "project_id": "PROJECT_ID",
  "project_target_id": "PROJECT_TARGET_ID",
  "channels": ["gmail_send", "linkedin_send_message", "supercarl_referral_request"]
}
```

```json
{
  "mode": "draft",
  "agent_session_id": "AGENT_SESSION_ID",
  "project_id": "PROJECT_ID",
  "project_target_id": "PROJECT_TARGET_ID",
  "channel": "linkedin_send_message",
  "message": "A reviewed-later draft grounded in cited evidence.",
  "evidence_ids": ["EVIDENCE_ID_1"],
  "approval_required": true
}
```

```json
{
  "mode": "update_message",
  "project_id": "PROJECT_ID",
  "agent_session_id": "AGENT_SESSION_ID",
  "project_target_id": "PROJECT_TARGET_ID",
  "message": "The exact reviewed-later draft to save.",
  "review_action": "save",
  "user_confirmed": true
}
```

```json
{
  "mode": "send",
  "agent_session_id": "AGENT_SESSION_ID",
  "project_id": "PROJECT_ID",
  "project_target_id": "PROJECT_TARGET_ID",
  "channel": "linkedin_send_message",
  "message": "The exact reviewed message the user approved.",
  "user_confirmed": true
}
```

## Draft Evaluation

Before presenting a draft, check:

- the opener cites a real evidence item;
- the value is useful for the recipient;
- tone matches the user's role intent, such as job seeker, recruiter, founder, or sales;
- warm intro language is supported by social proximity evidence;
- channel is allowed by `precheck`;
- history does not show a recent unanswered message that would make the draft feel spammy.

## Guardrails

- Never call `send_communication` with `mode: "send"` unless the user explicitly approves that exact project target, channel, and message.
- Never skip `send_communication` `precheck` and `history` before an approved project-target send.
- Bind all project, target, and outreach calls with `agent_session_id`.
- Prefer project-native `generate_messages` for grouped outreach.
- Do not use unsupported engagement modes such as calls or call-rate flows; prefer `quick_text` and `schedule_live` when available.
- Do not draft from generic match reasons alone. Require evidence.
- If the user asks to keep monitoring after outreach review, use `watch_signals` through the appropriate watch skill.
- Keep all outreach approval-gated.
