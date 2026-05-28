---
name: super-carl-post-activity-to-prospects
description: Search recent posts or engagement now, identify ICP-fit people behind the activity, inspect evidence, and add selected prospects to review.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, recruiter, networking]
    primary_tool: posts_search
---

# Super Carl Post Activity To Prospects

Use this when the user wants to search current post activity now: people engaging with the user's posts, competitor posts, category conversations, recruiter posts, or employee posts. It should group useful people in a project and can generate evidence-backed personal messages. This is a direct MCP workflow, not a hosted watch.

## Flow

1. Start or bind an `agent_session`; switch to an existing project when the user names one.
2. Call `posts_search` with `agent_session_id`, the topic, author/source scope, time window, and `with_people: true`.
3. Ask for post URLs or snippets, actor identity, engagement type, timestamp, ICP or candidate-fit reason, and social proximity.
4. Use `people_search` with the same `agent_session_id` to enrich high-fit actors when the post result does not include enough person evidence.
5. Use `project_action` with `mode: "add_targets"` to group selected people in the project only after evidence inspection.
6. After adding targets, the normal next step is value-led message drafting. If the user asks for personalized outreach, use `project_action` `generate_messages` for grouped targets or project-bound `send_communication` `precheck` / `history` / `draft` for one exact target.
7. If the user asks for ongoing monitoring of posts or engagement, switch to a watch skill such as `super-carl-owned-audience-follow-up` or `super-carl-competitor-engagement-watch`.

## Example Direct Flow

```json
{
  "query": "people who engaged with competitor posts about GTM monitoring in the last 14 days",
  "agent_session_id": "AGENT_SESSION_ID",
  "with_people": true,
  "role_intent": "sales",
  "evidence_required": true,
  "limit": 10
}
```

```json
{
  "mode": "add_targets",
  "agent_session_id": "AGENT_SESSION_ID",
  "target_user_ids": ["PERSON_ID_1"],
  "outreach_intent_type": "finding_customers",
  "outreach_intent_description": "Share a useful resource related to the topic they engaged with.",
  "user_confirmed": true,
  "reason": "Engaged with cited competitor post and matches ICP",
  "approval_required": true
}
```

## Message Guidance

Lead with value and avoid surveillance language. Good drafts refer to the topic or useful resource when evidence supports it, not the fact that the person was tracked.

## Guardrails

- Do not fabricate post engagement details.
- Bind search, project grouping, and outreach work with `agent_session_id`.
- Do not treat likes or comments as purchase intent without stronger evidence.
- Do not send by default; use grouped project drafts or outreach review for `send_communication` draft flows, then send only after explicit approval.
- Keep all outreach approval-gated.
- Use `watch_signals` only when the user asks to keep monitoring.
