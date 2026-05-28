---
name: super-carl-job-search-warm-path
description: Run an immediate Super Carl job search against the user's profile, find hiring managers or warm paths, and add selected opportunities to review.
license: MIT
metadata:
  super_carl:
    role_intents: [job_seeker]
    primary_tool: jobs_search
---

# Super Carl Job Search Warm Path

Use this when a job seeker wants jobs now, ranked by fit against their profile and by reachable people who can help. It should group promising jobs and people in a Super Carl project and optionally draft personalized intro requests. This is a direct MCP workflow, not a hosted watch.

## Flow

1. Start or bind an `agent_session`; if the user names an existing job-search project, switch the session to that project.
2. Call `jobs_search` with `agent_session_id`, the user's target role, geography, remote preference, industry scope, exclusions, and `with_people: true`.
3. Ask Super Carl to rank beyond title overlap: profile experience, seniority, domain background, job requirements, company context, and evidence citations.
4. For strong jobs, use `people_search` or `social_proximity_research` with the same `agent_session_id` to find up to three hiring managers, recruiters, alumni, prior coworkers, or leadership paths.
5. Use `project_action` with `mode: "add_targets"` to group selected reachable people in the project. If no project is bound, Super Carl creates or uses the current MCP session project.
6. After adding reachable people, the normal next step is an intro-request draft. When the user asks for intro notes, use `project_action` with `mode: "generate_messages"` and outreach intent such as `reaching_hiring_manager`; this creates reviewable personalized messages without sending.
7. If the user wants to keep watching for new roles, switch to `super-carl-job-seeker-opportunity-watch` after the direct run.

## Example Direct Flow

```json
{
  "query": "VP Engineering or Director Engineering roles in AI infrastructure and developer tools",
  "agent_session_id": "AGENT_SESSION_ID",
  "with_people": true,
  "fit_profile": "Use my Super Carl profile and engineering leadership background",
  "exclude_functions": ["human resources", "finance", "legal"],
  "evidence_required": true,
  "limit": 10
}
```

```json
{
  "query": "hiring managers, engineering leaders, recruiters, and warm paths for JOB_ID_1",
  "agent_session_id": "AGENT_SESSION_ID",
  "role_intent": "job_seeker",
  "company_ids": ["COMPANY_ID_1"],
  "include_social_proximity": true,
  "limit": 6
}
```

```json
{
  "mode": "generate_messages",
  "agent_session_id": "AGENT_SESSION_ID",
  "outreach_intent_type": "reaching_hiring_manager",
  "outreach_intent_description": "Ask for advice or a warm intro about a role that matches my engineering leadership background.",
  "user_confirmed": true
}
```

## Message Guidance

If the user asks for an intro note, draft only after the job evidence and warm-path evidence are available. The draft should connect the user's background to the role and ask for a specific, low-friction next step.

## Guardrails

- Do not recommend jobs based on title alone.
- Bind searches, project actions, and drafts with `agent_session_id`.
- Exclude functions that conflict with the user's profile, such as HR roles for an engineering leader, unless the user explicitly asks for them.
- Do not invent hiring managers or warm paths.
- Do not call `send_communication` with `mode: "send"` from this skill.
- Keep outreach approval-gated, and use `watch_signals` only when the user asks to keep monitoring.
