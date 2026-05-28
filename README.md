# Super Carl Agent Skills

Portable workflow skills for using Super Carl MCP/API from agent runtimes such as OpenClaw, Hermes Agent, Codex, Claude, and other MCP clients.

These skills are intentionally workflow-oriented. Direct skills help an agent search now, inspect evidence, add targets to projects, and prepare approval-gated drafts. Watch skills create or update durable Super Carl `watch_signals` projects for work that should continue over time.

## Install Shape

Each folder under `skills/` is an AgentSkills-style skill with a `SKILL.md` file. Runtimes that support local skill directories can point at this repository or copy individual skill folders into their local skills root.

## Core Contract

- Use direct MCP tools for immediate work: `agent_session`, `people_search`, `company_search`, `jobs_search`, `posts_search`, `social_proximity_research`, `project_action`, and `send_communication`.
- Use `watch_signals` when the user asks Carl to keep monitoring, notify on changes, or run a recurring Scan My Network project.
- Anchor every watch and project action to a `project_id` when possible.
- Treat `agent_webhook` as an optional notification channel, not the scheduler of record.
- Use cited evidence before writing outreach.
- Route action-ready people through `project_action`, `promote_hit`, or project review actions.
- Never send outreach without the user's explicit approval.

## Skill Families

- Direct search: find people, jobs, companies, or post activity now.
- Direct outreach review: load project targets, inspect evidence, run channel prechecks, fetch history, and draft messages.
- Hosted watches: create or update durable `watch_signals` projects and inspect hits over time.
- Hybrid: run direct search first, then create a watch if the user wants ongoing monitoring.

## Validation

```bash
python3 scripts/validate_skills.py
python3 scripts/simulate_user_flows.py
```

The local validator checks frontmatter shape, unique names, description length, supported MCP tool mentions, and basic safety wording. The simulation harness runs deterministic OpenClaw and Hermes Agent user-flow simulations against mocked direct MCP tools and a mocked `watch_signals` surface. OpenClaw and Hermes Agent validation commands are listed in `references/validation.md`.

For live stochastic runtime checks with real LLM calls:

```bash
python3 scripts/live_agent_runtime_flows.py --runtime hermes-agent --runtime openclaw
```

The live harness uses `OPENAI_API_KEY` from `../social-connector/.env`, runs actual Hermes Agent and OpenClaw agent loops against local mocked Super Carl MCP tool surfaces, and compares emitted tool-call traces to the same contract.
