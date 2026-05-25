---
name: super-carl-champion-mover
description: Configure a hosted Super Carl watch for former champions, customers, coworkers, advisors, investors, or target contacts changing roles with warm-path evidence.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, investor, networking]
    primary_tool: watch_signals
---

# Super Carl Champion Mover

Use this when the user wants to watch trusted people or prior champions for role changes and create timely, relationship-aware follow-ups.

## Flow

1. Use the Super Carl MCP tool `watch_signals`; identify the people list, relationship context, ICP, and desired follow-up style.
2. Use `people_list`, `project`, `spreadsheet`, or `network_scope` sources.
3. Use signals `role_change`, `company_growth`, `warm_intro`, and `follow_up`.
4. Ask Super Carl to cite the profile-change evidence, old/new company when known, relationship path, and why this is timely.
5. Use `hits` and `evidence` before drafting.
6. Use `promote_hit` for reviewable follow-up drafts.

## Example Create

```json
{
  "mode": "create",
  "title": "Champion mover watch",
  "role_intent": "networking",
  "source_kind": "people_list",
  "sources": [
    { "source_kind": "people_list", "value": "Former customers, advisors, and coworkers" },
    { "source_kind": "network_scope", "value": "Use social proximity and previous relationship evidence" }
  ],
  "watch_prompt": "Watch for former champions and trusted contacts changing roles. Surface people where a congratulations note or value-first follow-up would be well received.",
  "signal_types": ["role_change", "follow_up", "warm_intro"],
  "delivery_channels": ["project_feed", "app_push", "email_digest"],
  "freshness_policy": {
    "profile_updates": "weekly_or_when_new_bulk_ingest_arrives"
  },
  "action_policy": {
    "default_action": "draft_message",
    "never_send_without_approval": true
  }
}
```

## Message Guidance

Start with the relationship and the role-change evidence. Keep it human: "Congrats on the move to X..." before offering help or context.

## Guardrails

- Profile updates may follow a weekly ingest cadence; do not promise tighter freshness than status reports show.
- Fetch `evidence` before naming a role change.
- Keep outreach approval-gated.
