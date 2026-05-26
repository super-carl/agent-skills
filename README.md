# Super Carl Agent Skills

Portable workflow skills for configuring hosted Super Carl `watch_signals` projects from agent runtimes such as OpenClaw, Hermes Agent, Codex, Claude, and other MCP clients.

These skills are intentionally workflow-oriented. They do not ask an agent to run a background loop. The agent helps the user express intent, creates or updates a durable Super Carl watch, then inspects hits, evidence, delivery status, and review-safe next actions through MCP/API.

## Install Shape

Each folder under `skills/` is an AgentSkills-style skill with a `SKILL.md` file. Runtimes that support local skill directories can point at this repository or copy individual skill folders into their local skills root.

## Core Contract

- Use the Super Carl MCP tool `watch_signals`.
- Anchor every watch to a `project_id` when possible.
- Treat `agent_webhook` as an optional notification channel, not the scheduler of record.
- Use `hits` and `evidence` before writing outreach.
- Route action-ready people through `promote_hit` or project review actions.
- Never send outreach without the user's explicit approval.

## Validation

```bash
python3 scripts/validate_skills.py
python3 scripts/simulate_user_flows.py
```

The local validator checks frontmatter shape, unique names, description length, and basic safety wording. The simulation harness runs deterministic OpenClaw and Hermes Agent user-flow simulations against a mocked `watch_signals` MCP surface. OpenClaw and Hermes Agent validation commands are listed in `references/validation.md`.
