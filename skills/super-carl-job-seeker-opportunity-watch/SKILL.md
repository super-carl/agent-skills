---
name: super-carl-job-seeker-opportunity-watch
description: Configure a hosted Super Carl watch for job seekers that matches new jobs, hiring managers, recruiters, company momentum, and warm paths against the user's profile.
license: MIT
metadata:
  super_carl:
    role_intents: [job_seeker]
    primary_tool: watch_signals
---

# Super Carl Job Seeker Opportunity Watch

Use this when the user wants Carl to monitor roles, companies, recruiters, and warm paths over time based on their own profile and target narrative.

## Flow

1. Use the Super Carl MCP tool `watch_signals`; capture target role, level, geography, remote preference, company stage, must-have exclusions, and cadence.
2. Use sources `owner_profile`, `account_list`, `job_search`, and `network_scope`.
3. Use signals `jobs`, `employee_post`, `company_growth`, and `warm_intro`.
4. Ask Super Carl to cite job URLs, matched requirements, profile-fit facts, hiring-manager/recruiter evidence, and warm paths.
5. Use `hits` and `evidence` before drafting intro requests or application notes.
6. Use `promote_hit` only when the user wants the opportunity in a project review queue.

## Example Create

```json
{
  "mode": "create",
  "title": "Senior product roles worth applying to",
  "role_intent": "job_seeker",
  "source_kind": "owner_profile",
  "sources": [
    { "source_kind": "owner_profile", "value": "Use my Super Carl profile and work history" },
    { "source_kind": "account_list", "value": "AI infrastructure, developer tools, and data platforms" },
    { "source_kind": "network_scope", "value": "Hiring managers, recruiters, alumni, and coworkers" }
  ],
  "watch_prompt": "Find new senior product roles that match my background. Rank jobs by fit, company momentum, and reachable hiring paths. Send a digest when there are new strong matches.",
  "signal_types": ["jobs", "employee_post", "company_growth", "warm_intro"],
  "delivery_channels": ["project_feed", "email_digest"],
  "action_policy": {
    "default_action": "draft_intro_request",
    "never_send_without_approval": true
  }
}
```

## Message Guidance

Drafts should connect the user's profile to the role. Prefer warm intro requests when social proximity is strong; otherwise draft concise recruiter or hiring-manager notes with evidence-backed fit.

## Guardrails

- Do not overstate qualifications that are not in the user's profile evidence.
- Use `evidence` before recommending a job.
- Keep application notes and outreach approval-gated.
