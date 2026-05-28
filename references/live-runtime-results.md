# Live Runtime Results

Latest focused live runs used `gpt-4.1-mini` with `OPENAI_API_KEY` loaded from `../social-connector/.env`.

## Harness

- `scripts/live_agent_runtime_flows.py` runs Hermes Agent directly through `AIAgent` and OpenClaw through `runEmbeddedPiAgent`.
- Hermes registers mocked Super Carl MCP tools in its real tool registry.
- OpenClaw creates a temporary local plugin exposed through `plugins.load.paths`.
- Both runtimes write tool-call traces and compare them against `scripts/simulate_user_flows.py` contract assertions.
- This exercises real agent/tool loops with a mocked MCP-compatible tool surface. It does not yet exercise a standalone stdio or HTTP MCP transport process.

## Findings And Fixes

- Job seeker flow: both runtimes initially implied job search through the `jobs` signal but omitted the `job_search` source. The skill now marks `job_search` as required and the example includes it.
- Agent webhook flow: Hermes sometimes treated webhook setup as outreach prep and called `promote_hit`. The skill now says webhook setup is delivery-status only and must not promote hits.
- Agent webhook fallback inspection: OpenClaw once called `evidence` without a concrete `signal_hit_id`. The skill and harness prompt now require `hits` before `evidence` and a concrete `signal_hit_id`.
- Competitor engagement: Hermes once omitted `action_policy` on create. The skill and harness prompt now require approval policy at watch creation time for outreach-capable watches.
- Direct ICP search: OpenClaw initially stopped after `people_search` because mocked results looked like engineering leaders instead of sales/RevOps ICPs. The mock now returns role-appropriate profiles so the direct skill can continue into `project_action add_targets` and `generate_messages`.
- Direct job search: OpenClaw sometimes relies on `jobs_search(with_people=true)` rather than a separate `people_search` warm-path pass. The contract now accepts this when the job tool returns people and the agent still groups targets and generates messages.
- Project outreach review: both runtimes now keep `send_communication` project-bound. Draft flows run `precheck`, `history`, optional `people_lookup_batch`, `draft`, and save back through `project_action update_message`.
- Explicit single-target send: Hermes initially skipped `precheck` and `history`. The skill now states that even an approved project-target send must run project-bound `precheck` and `history` first unless those checks already happened in the current trace.

## Passing Focused Reruns

```text
runtime       scenario                            calls  modes
------------  ----------------------------------  -----  ----------------------------------------
hermes-agent  job_seeker_profile_matched_roles    5      create,run_now,hits,evidence,promote_hit
openclaw      job_seeker_profile_matched_roles    5      create,run_now,hits,evidence,promote_hit
hermes-agent  agent_webhook_digest_delivery       3      status,update,delivery_status
openclaw      agent_webhook_digest_delivery       2      update,delivery_status
hermes-agent  competitor_engagement_icp_followup  5      create,run_now,hits,evidence,promote_hit
openclaw      competitor_engagement_icp_followup  4      create,hits,evidence,promote_hit
```

Direct invocation focused reruns:

```text
runtime       scenario                                      calls  modes
------------  --------------------------------------------  -----  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
openclaw      direct_icp_people_search_to_project_messages  4      agent_session.start,people_search,project_action.add_targets,project_action.generate_messages
openclaw      direct_job_search_warm_path_messages          4      agent_session.start,jobs_search,project_action.add_targets,project_action.generate_messages
openclaw      direct_project_outreach_review_single_target  7      agent_session.start,project_action.targets,send_communication.precheck,send_communication.history,people_lookup_batch,send_communication.draft,project_action.update_message
openclaw      direct_project_outreach_explicit_single_send  6      agent_session.list,project_action.targets,send_communication.precheck,send_communication.history,send_communication.draft,send_communication.send
hermes-agent  direct_icp_people_search_to_project_messages  4      agent_session.start,people_search,project_action.add_targets,project_action.generate_messages
hermes-agent  direct_job_search_warm_path_messages          5      agent_session.start,jobs_search,people_search,project_action.add_targets,project_action.generate_messages
hermes-agent  direct_project_outreach_review_single_target  7      agent_session.start,project_action.targets,send_communication.precheck,send_communication.history,people_lookup_batch,send_communication.draft,project_action.update_message
hermes-agent  direct_project_outreach_explicit_single_send  8      agent_session.status,project_action.targets,send_communication.precheck,send_communication.history,send_communication.draft,send_communication.precheck,send_communication.history,send_communication.send
```
