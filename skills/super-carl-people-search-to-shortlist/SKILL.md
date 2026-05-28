---
name: super-carl-people-search-to-shortlist
description: Run an immediate Super Carl people search, inspect cited evidence and social proximity, then add approved high-fit people to a project shortlist.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, recruiter, investor, bd, networking]
    primary_tool: people_search
---

# Super Carl People Search To Shortlist

Use this when the user wants to find ICPs or other people now, compare evidence, group selected targets in a Super Carl project, and optionally generate personalized outreach drafts. This is a direct MCP workflow, not a hosted watch.

## Flow

1. Start or bind an `agent_session`; if the user names an existing project, call `agent_session` with `mode: "switch_project"` so later calls are project-bound.
2. Call `people_search` with the user's role intent, target description, exclusions, project context, and `agent_session_id`. Ask for evidence, match reasons, and `social_proximity` when warm paths matter.
3. If the user asks for companies first, use `company_search` before `people_search`; otherwise keep the flow person-first.
4. Review results by inspecting match reasons, citations, current role facts, source data, and social proximity. Do not rely on title alone.
5. Use `project_action` with `mode: "add_targets"` and `agent_session_id` to add approved targets. If no project is bound, Super Carl creates or uses the current MCP session project.
6. After adding targets, the normal next step is message drafting. When the user asks for outreach grouping or personalized messages, use `project_action` with `mode: "generate_messages"` after targets are grouped. This drafts project messages; it does not send.
7. Use `project_action` with `mode: "send_readiness"` to summarize what is ready for review, then offer to send reviewed project outreach only after explicit approval.
8. If the user asks Carl to keep monitoring, switch to a watch skill and create a `watch_signals` project only after the direct search is complete.

## Example Direct Flow

```json
{ "mode": "start", "agent_name": "OpenClaw ICP search" }
```

```json
{
  "query": "VP Sales and RevOps leaders at Series A AI infrastructure companies in San Francisco",
  "role_intent": "sales",
  "agent_session_id": "AGENT_SESSION_ID",
  "include_social_proximity": true,
  "evidence_required": true,
  "limit": 10
}
```

```json
{
  "mode": "add_targets",
  "agent_session_id": "AGENT_SESSION_ID",
  "target_user_ids": ["PERSON_ID_1", "PERSON_ID_2"],
  "engagement_mode": "quick_text",
  "outreach_intent_type": "finding_customers",
  "outreach_intent_description": "Offer useful GTM monitoring context to likely ICP buyers.",
  "user_confirmed": true,
  "approval_required": true
}
```

```json
{
  "mode": "generate_messages",
  "agent_session_id": "AGENT_SESSION_ID",
  "outreach_intent_type": "finding_customers",
  "outreach_intent_description": "Offer useful GTM monitoring context to likely ICP buyers.",
  "user_confirmed": true
}
```

## Message Guidance

For a group of selected targets, prefer `project_action` `generate_messages` so drafts are grouped in the project and reviewed together. For one exact project target, hand off to `super-carl-project-outreach-review` so `send_communication` can run project-bound `precheck`, `history`, `draft`, and an explicit `send` if the user approves the exact message.

## Guardrails

- Do not send from this skill.
- Bind all related calls with `agent_session_id` and a project when available.
- Do not add targets whose evidence is weak or mismatched to the user's intent.
- Do not infer warm intros unless Super Carl returns social proximity evidence.
- Do not create a `watch_signals` watch unless the user asks Carl to keep monitoring over time.
- Keep all outreach approval-gated.
