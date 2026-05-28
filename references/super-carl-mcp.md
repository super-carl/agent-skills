# Super Carl MCP Reference

Use this reference from any Super Carl skill.

## Website And Docs

- Website: https://supercarl.ai
- API docs: https://supercarl.ai/docs

## Direct Tools

Use direct MCP tools when the user wants an answer or action now.

- `agent_session`: start or bind an external-agent session. Pass the session context through later calls when available.
- `people_search`: find people from a natural-language target description, filters, relationship context, and role intent. Use for "who should I talk to" flows.
- `company_search`: find companies first when the request is account/company-led.
- `jobs_search`: find jobs and, when useful, set `with_people: true` so Super Carl can include hiring managers, recruiters, alumni, or warm paths.
- `posts_search`: search post/activity signals and, when useful, set `with_people: true` to identify the people behind the activity.
- `people_lookup_batch`: hydrate known people from URLs, ids, or imported lists.
- `social_proximity_research`: inspect warm intro paths and relationship evidence for selected people.
- `project_action`: create projects, load project targets, add targets, update review status, or route selected results into a project.
- `send_communication`: run approval-gated communication flows with `precheck`, `history`, `draft`, `status`, `cancel`, and explicit `send`.

Direct tool rule: call `agent_session` first, bind the session to a project when the user names one, pass `agent_session_id` through related calls, search and inspect evidence, route selected targets through `project_action`, and use `send_communication` only after channel precheck and history. Never make `send` the default.

For grouped outreach, prefer project-native actions:

- `project_action` `mode: "add_targets"` groups approved people in the project shortlist.
- `project_action` `mode: "generate_messages"` creates personalized drafts for selected or all project targets. This does not deliver messages.
- `project_action` `mode: "send_readiness"` summarizes reviewed, stale, edited, and ready targets before activation.
- `project_action` `mode: "activate"` starts project delivery only after explicit user approval.

For one exact target, use project-bound `send_communication` `precheck` -> `history` -> optional `people_lookup_batch` outreach context -> `draft`. Use `project_action` `update_message` when saving exact per-target copy back to a project. After a draft is saved, the normal next action is an explicit user decision to send, schedule, revise, or skip. `send_communication` `mode: "send"` is supported for a single project target only after the user approves the exact target, channel, and message. Even for an already approved draft, run project-bound `precheck` and `history` first unless those checks already happened in the current trace.

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

Do not send outreach directly from a skill. Fetch evidence, explain why the person or hit surfaced, route the target to project review, and keep delivery approval-gated inside Super Carl.

Direct skills should use `send_communication` in `precheck`, `history`, and `draft` modes. Only call `send` when the user explicitly approves the exact send.

## Evidence Rule

Good draft context names the source evidence:

- post URL or snippet;
- liked/commented/reposted event;
- job URL and matched requirement;
- company or profile change;
- source spreadsheet row;
- social proximity or warm intro path.

If evidence is missing or weak, ask the user whether to keep watching, broaden the source, or dismiss the hit.

## Choosing Direct Search Vs Watch

- Use direct search when the user asks "find", "show me", "draft for these people", or "add the best matches now".
- Use a watch when the user asks "keep watching", "notify me", "daily/weekly if changed", "monitor over time", or "run when new data arrives".
- Use a hybrid when the user wants both: run direct search first, then create a `watch_signals` project for ongoing changes.
