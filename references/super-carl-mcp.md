# Super Carl MCP Reference

Use this reference from any Super Carl skill.

## Website And Docs

- Website: https://supercarl.ai
- API docs: https://supercarl.ai/docs

## Tool: `watch_signals`

Primary modes:

- `role_packs`: list role and intent packs.
- `create`: create a hosted Scan My Network watch.
- `update`: update an existing watch config.
- `status`: list active watch configs for a project.
- `hits`: list signal hits.
- `evidence`: fetch inspectable evidence for a hit.
- `delivery_status`: inspect project feed, app push, email digest, MCP stream, and `agent_webhook` delivery.
- `run_now`: ask Super Carl to run the watch now.
- `pause` / `resume`: manage active watching when budget, credits, or intent changes.
- `promote_hit`: add a hit to the project review queue and optionally draft a message.
- `dismiss_hit` / `snooze_hit`: cleanly manage noisy hits.

Durable watch fields:

- `project_id`: public project id. Internally this may map to an assignment id.
- `role_intent`: one of `gtm`, `founder`, `sales`, `job_seeker`, `recruiter`, `investor`, `bd`, `networking`, `general`.
- `sources`: durable source refs such as Google Sheets, account lists, competitor sets, people lists, owner profile, owner posts, owned audience, and network scope.
- `signal_types`: `liked_my_post`, `competitor_engagement`, `role_change`, `jobs`, `employee_post`, `company_growth`, `hiring_spike`, `warm_intro`, `follow_up`, `posts`.
- `delivery_channels`: include `project_feed` by default; add `agent_webhook` only when a reliable callback endpoint is configured.
- `callback_policy`: include `callback_id`, `mcp_connection_id`, and event types when using `agent_webhook`.

## Outreach Rule

Do not send outreach directly from a skill. Fetch evidence, explain why the hit surfaced, promote the hit to project review, and keep delivery approval-gated inside Super Carl.

## Evidence Rule

Good draft context names the source evidence:

- post URL or snippet;
- liked/commented/reposted event;
- job URL and matched requirement;
- company or profile change;
- source spreadsheet row;
- social proximity or warm intro path.

If evidence is missing or weak, ask the user whether to keep watching, broaden the source, or dismiss the hit.
