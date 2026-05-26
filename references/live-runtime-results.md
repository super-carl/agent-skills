# Live Runtime Results

Latest focused live runs used `gpt-4.1-mini` at temperature `0.7` with `OPENAI_API_KEY` loaded from `../social-connector/.env`.

## Harness

- `scripts/live_agent_runtime_flows.py` runs Hermes Agent directly through `AIAgent` and OpenClaw through `runEmbeddedPiAgent`.
- Hermes registers `watch_signals` in its real tool registry.
- OpenClaw creates a temporary local plugin exposed through `plugins.load.paths`.
- Both runtimes write tool-call traces and compare them against `scripts/simulate_user_flows.py` contract assertions.
- This exercises real agent/tool loops with a mocked MCP-compatible tool surface. It does not yet exercise a standalone stdio or HTTP MCP transport process.

## Findings And Fixes

- Job seeker flow: both runtimes initially implied job search through the `jobs` signal but omitted the `job_search` source. The skill now marks `job_search` as required and the example includes it.
- Agent webhook flow: Hermes sometimes treated webhook setup as outreach prep and called `promote_hit`. The skill now says webhook setup is delivery-status only and must not promote hits.
- Agent webhook fallback inspection: OpenClaw once called `evidence` without a concrete `signal_hit_id`. The skill and harness prompt now require `hits` before `evidence` and a concrete `signal_hit_id`.
- Competitor engagement: Hermes once omitted `action_policy` on create. The skill and harness prompt now require approval policy at watch creation time for outreach-capable watches.

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
