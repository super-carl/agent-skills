---
name: super-carl-recruiter-candidate-radar
description: Configure a hosted Super Carl watch for recruiters to monitor candidates, competitor alumni, role changes, hiring-manager context, and team warm paths.
license: MIT
metadata:
  super_carl:
    role_intents: [recruiter]
    primary_tool: watch_signals
---

# Super Carl Recruiter Candidate Radar

Use this when a recruiter wants Carl to watch candidate lists, competitor alumni, transition signals, or hiring-manager context and produce reviewable candidate shortlists.

## Flow

1. Use the Super Carl MCP tool `watch_signals`; capture role requirements, seniority, location, must-have skills, target companies, and excluded employers.
2. Use sources `spreadsheet`, `people_list`, `account_list`, and `network_scope`.
3. Use signals `role_change`, `employee_post`, `posts`, and `warm_intro`.
4. Ask for evidence that includes candidate profile facts, transition or openness signal, source row, and warm path.
5. Inspect `hits`, fetch `evidence`, and promote only high-fit candidates into project review.
6. Keep outreach approval-gated and respectful.

## Example Create

```json
{
  "mode": "create",
  "title": "Founding AI engineer candidate radar",
  "role_intent": "recruiter",
  "source_kind": "spreadsheet",
  "sources": [
    { "source_kind": "spreadsheet", "url": "https://docs.google.com/spreadsheets/d/example", "label": "Candidate and competitor source list" },
    { "source_kind": "network_scope", "value": "Team warm paths and prior coworkers" }
  ],
  "watch_prompt": "Watch for candidates with AI infra and distributed systems experience who changed roles, posted about relevant work, or have a warm team path. Rank by fit and likely openness.",
  "signal_types": ["role_change", "employee_post", "posts", "warm_intro"],
  "delivery_channels": ["project_feed", "email_digest"],
  "action_policy": {
    "default_action": "draft_message",
    "never_send_without_approval": true
  }
}
```

## Message Guidance

Drafts should lead with role relevance and a specific positive reason, not assumptions about job-search status. Mention transition evidence only when it is in `evidence`.

## Guardrails

- Do not infer sensitive or unsupported openness.
- Fetch `evidence` before drafting.
- Do not send recruiter outreach without approval.
