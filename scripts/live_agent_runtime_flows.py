#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CARL_APP_ROOT = ROOT.parent
SOCIAL_CONNECTOR_ENV = CARL_APP_ROOT / "social-connector" / ".env"
HERMES_ROOT = CARL_APP_ROOT / "hermes-agent-fresh"
OPENCLAW_ROOT = CARL_APP_ROOT / "openclaw-fresh"
TOOLSET_NAME = "super-carl-live-runtime"

DEFAULT_SCENARIOS = (
    "direct_icp_people_search_to_project_messages",
    "direct_job_search_warm_path_messages",
    "direct_project_outreach_review_single_target",
    "competitor_engagement_icp_followup",
    "agent_webhook_digest_delivery",
)


class LiveRuntimeFailure(RuntimeError):
    def __init__(self, message: str, partial: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.partial = partial or {}


def load_simulator_module() -> Any:
    simulator_path = ROOT / "scripts" / "simulate_user_flows.py"
    spec = importlib.util.spec_from_file_location("super_carl_simulator", simulator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {simulator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SIM = load_simulator_module()


def tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": True,
        },
    }


SUPER_CARL_TOOL_SCHEMAS = [
    tool_schema(
        "agent_session",
        "Mock Super Carl MCP tool to start, bind, switch project, check, or close an external agent session. Call this first for direct search/outreach flows and pass agent_session_id to later tools.",
        {
            "mode": {"type": "string", "enum": ["start", "bind", "list", "switch_project", "status", "close"]},
            "agent_name": {"type": "string"},
            "agent_session_id": {"type": "string"},
            "project_id": {"type": "string"},
            "search": {"type": "string"},
            "external_thread_ref": {"type": "string"},
        },
        ["mode"],
    ),
    tool_schema(
        "people_search",
        "Mock Super Carl people search. Use for immediate ICP, candidate, hiring-manager, warm-path, and shortlist discovery. Pass agent_session_id and evidence/social proximity options.",
        {
            "agent_session_id": {"type": "string"},
            "query": {"type": "string"},
            "role_intent": {"type": "string"},
            "company_ids": {"type": "array", "items": {"type": "string"}},
            "post_ids": {"type": "array", "items": {"type": "string"}},
            "include_social_proximity": {"type": "boolean"},
            "evidence_required": {"type": "boolean"},
            "limit": {"type": "integer"},
            "source_tool": {"type": "string"},
        },
    ),
    tool_schema(
        "company_search",
        "Mock Super Carl company search. Use before people_search when the request is company-led or requires company binding.",
        {"agent_session_id": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}},
    ),
    tool_schema(
        "jobs_search",
        "Mock Super Carl jobs search. Use with with_people=true when the user wants hiring managers, recruiters, or warm paths for job opportunities.",
        {
            "agent_session_id": {"type": "string"},
            "query": {"type": "string"},
            "with_people": {"type": "boolean"},
            "fit_profile": {"type": "string"},
            "exclude_functions": {"type": "array", "items": {"type": "string"}},
            "evidence_required": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
    ),
    tool_schema(
        "posts_search",
        "Mock Super Carl post/activity search. Use with with_people=true to pivot post engagement into ICP/candidate targets.",
        {
            "agent_session_id": {"type": "string"},
            "query": {"type": "string"},
            "with_people": {"type": "boolean"},
            "role_intent": {"type": "string"},
            "evidence_required": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
    ),
    tool_schema(
        "people_lookup_batch",
        "Mock Super Carl people lookup batch. Use relationship_detail='intro_paths' before personalized outreach when warm-path context matters.",
        {
            "agent_session_id": {"type": "string"},
            "profiles": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "relationship_detail": {"type": "string"},
        },
    ),
    tool_schema(
        "social_proximity_research",
        "Mock Super Carl social proximity research. Use for warm intro paths for selected people.",
        {
            "agent_session_id": {"type": "string"},
            "target_user_id": {"type": "string"},
            "status_only": {"type": "boolean"},
        },
    ),
    tool_schema(
        "project_action",
        "Mock Super Carl project tool. Use add_targets to group people, generate_messages for personalized grouped drafts, update_message for exact per-target draft saves, send_readiness before activation.",
        {
            "mode": {
                "type": "string",
                "enum": [
                    "list",
                    "status",
                    "targets",
                    "recipient_emails",
                    "metrics",
                    "send_readiness",
                    "add_targets",
                    "remove_targets",
                    "retry_failed_linkedin_sends",
                    "rename",
                    "update_engagement_mode",
                    "update_templates",
                    "generate_templates",
                    "generate_messages",
                    "update_message",
                    "activate",
                ],
            },
            "agent_session_id": {"type": "string"},
            "project_id": {"type": "string"},
            "project_target_id": {"type": "string"},
            "target_user_ids": {"type": "array", "items": {"type": "string"}},
            "target_user_id": {"type": "string"},
            "target_ids": {"type": "array", "items": {"type": "string"}},
            "engagement_mode": {"type": "string", "enum": ["quick_text", "schedule_live"]},
            "outreach_intent_type": {"type": "string"},
            "outreach_intent_description": {"type": "string"},
            "message": {"type": "string"},
            "review_action": {"type": "string"},
            "user_confirmed": {"type": "boolean"},
            "include_evidence": {"type": "boolean"},
        },
        ["mode"],
    ),
    tool_schema(
        "send_communication",
        "Mock Super Carl communication tool. Normally project-bound. Use precheck -> history -> draft; use send only after explicit user approval of the exact project target, channel, and message.",
        {
            "mode": {"type": "string", "enum": ["precheck", "history", "draft", "send", "status", "cancel"]},
            "agent_session_id": {"type": "string"},
            "project_id": {"type": "string"},
            "project_target_id": {"type": "string"},
            "target_user_id": {"type": "string"},
            "channels": {"type": "array", "items": {"type": "string"}},
            "requested_channels": {"type": "array", "items": {"type": "string"}},
            "channel": {"type": "string"},
            "message": {"type": "string"},
            "subject": {"type": "string"},
            "history_fresh": {"type": "boolean"},
            "user_confirmed": {"type": "boolean"},
            "approval_required": {"type": "boolean"},
        },
        ["mode"],
    ),
    tool_schema(
        "watch_signals",
        "Mock Super Carl MCP tool for Scan My Network watch projects. Use for durable watches, run checks, hits/evidence, promotion, and agent webhook delivery.",
        {
            "mode": {
                "type": "string",
                "enum": [
                    "role_packs",
                    "create",
                    "update",
                    "run_now",
                    "hits",
                    "evidence",
                    "promote_hit",
                    "delivery_status",
                    "status",
                    "pause",
                    "resume",
                    "dismiss_hit",
                    "snooze_hit",
                ],
            },
            "project_id": {"type": "string"},
            "watch_config_id": {"type": "string"},
            "title": {"type": "string"},
            "role_intent": {"type": "string"},
            "source_kind": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "watch_prompt": {"type": "string"},
            "signal_types": {"type": "array", "items": {"type": "string"}},
            "delivery_channels": {"type": "array", "items": {"type": "string"}},
            "callback_policy": {"type": "object", "additionalProperties": True},
            "freshness_policy": {"type": "object", "additionalProperties": True},
            "action_policy": {"type": "object", "additionalProperties": True},
            "estimated_preview_searches_per_run": {"type": "integer"},
            "signal_hit_id": {"type": "string"},
            "draft_message": {"type": "boolean"},
            "actions": {"type": "array", "items": {"type": "string"}},
        },
        ["mode"],
    ),
]

SUPER_CARL_TOOL_SCHEMAS_BY_NAME = {schema["name"]: schema for schema in SUPER_CARL_TOOL_SCHEMAS}


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def load_openai_key() -> str:
    env = parse_env_file(SOCIAL_CONNECTOR_ENV)
    api_key = os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(f"OPENAI_API_KEY missing from environment or {SOCIAL_CONNECTOR_ENV}")
    os.environ.setdefault("OPENAI_API_KEY", api_key)
    return api_key


def selected_scenarios(names: list[str] | None) -> list[Any]:
    known = {scenario.name: scenario for scenario in SIM.SCENARIOS}
    requested = names or list(DEFAULT_SCENARIOS)
    unknown = set(requested) - set(known)
    if unknown:
        raise ValueError(f"Unknown scenario(s): {', '.join(sorted(unknown))}")
    return [known[name] for name in requested]


def skill_text(scenario: Any) -> str:
    path = ROOT / "skills" / scenario.skill / "SKILL.md"
    return path.read_text()


class LiveMockSuperCarlMCP(SIM.MockSuperCarlMCP):
    def call(self, tool: str, request: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_tool_args(request)
        return super().call(tool, normalized)


def normalize_tool_args(args: Any) -> dict[str, Any]:
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return {"mode": "status", "raw": args}
    if not isinstance(args, dict):
        return {"mode": "status", "raw": args}
    if "mode" not in args and isinstance(args.get("request"), dict):
        return deepcopy(args["request"])
    return deepcopy(args)


def build_system_prompt(runtime: str) -> str:
    return f"""
You are running inside the {runtime} agent runtime for a live stochastic Super Carl skill validation.

Use the available Super Carl MCP tools whenever the user request requires search, project grouping, outreach review, or hosted watching. Do not answer only in prose when a tool call is needed.

Contract:
- For direct skills, start with `agent_session` mode="start" and pass the returned `agent_session_id` to later search, project, and communication tools.
- Direct skills should bind work to a project through `agent_session` mode="switch_project" when a project is named, or through `project_action` mode="add_targets" with `agent_session_id` when grouping selected targets.
- If the user refers to the current or selected Super Carl project without giving an id, use the current `agent_session_id` with `project_action` rather than asking for a project id.
- After adding targets, the normal next action is a project-bound draft: use `project_action` mode="generate_messages" for grouped outreach, or project-bound `send_communication` mode="precheck" -> mode="history" -> mode="draft" for one exact target.
- `send_communication` mode="send" is allowed only when the user explicitly approved the exact target, channel, and message; pass `user_confirmed: true` and project/target identifiers.
- Even for an explicitly approved send, call project-bound `send_communication` mode="precheck" and mode="history" before mode="send" unless those exact checks already happened in the same trace.
- In this validation harness, a user request that says add, group, generate, draft, save, or send is explicit approval for that requested mutating step. Pass `user_confirmed: true` for requested project mutations, but still do not send unless the prompt says send or approved.
- `project_action` mode="update_message" is mutating; include `user_confirmed: true` when saving the requested draft.
- For job and post searches that ask for people, pass `with_people: true`.
- For watch skills, create or update a durable watch with `watch_signals` mode="create" or mode="update" when the skill configures a watch.
- For watch hits, use `hits` and then `evidence` before `promote_hit`; every `evidence` call must include a concrete `signal_hit_id` from a prior `hits` result.
- When creating or updating a watch that can lead to outreach or project actions, include `action_policy.never_send_without_approval: true`.
- If the active watch skill says the flow is delivery/status-only or says not to promote hits, do not call `promote_hit`.
- Preserve `project_feed` when enabling `agent_webhook`.
""".strip()


def build_user_prompt(scenario: Any) -> str:
    return f"""
Load and follow this Super Carl skill:

<skill>
{skill_text(scenario)}
</skill>

User request:
{scenario.user_prompt}

Run the workflow now against the mock Super Carl MCP tools. Use direct search/project/communication tools for direct skills and `watch_signals` for hosted watch skills. Stop after the requested search, project grouping, draft, approved send, or watch/action setup is complete.
""".strip()


def validate_live_calls(scenario: Any, runtime: str, calls: list[dict[str, Any]]) -> None:
    normalized = [normalize_tool_args(call) for call in calls]
    SIM.assert_scenario(scenario, runtime, normalized)


def run_hermes_scenario(scenario: Any, model: str, temperature: float, max_iterations: int) -> dict[str, Any]:
    if not HERMES_ROOT.exists():
        raise RuntimeError(f"Hermes checkout missing: {HERMES_ROOT}")
    load_openai_key()
    if str(HERMES_ROOT) not in sys.path:
        sys.path.insert(0, str(HERMES_ROOT))

    from run_agent import AIAgent
    from tools.registry import registry
    from toolsets import create_custom_toolset

    mock = LiveMockSuperCarlMCP(scenario.name, "hermes-agent")
    tool_starts: list[dict[str, Any]] = []
    tool_completions: list[dict[str, Any]] = []

    def make_handler(tool_name: str):
        def handler(args: dict[str, Any], **_kwargs: Any) -> str:
            response = mock.call(tool_name, args)
            return json.dumps(response, sort_keys=True)
        return handler

    def register_tool(schema: dict[str, Any]) -> None:
        registry.register(
            name=schema["name"],
            toolset=TOOLSET_NAME,
            schema=schema,
            handler=make_handler(schema["name"]),
            description=schema["description"],
            override=True,
        )

    for schema in SUPER_CARL_TOOL_SCHEMAS:
        register_tool(schema)

    create_custom_toolset(
        TOOLSET_NAME,
        "Live Super Carl runtime validation toolset with mocked MCP tool surfaces.",
        tools=[schema["name"] for schema in SUPER_CARL_TOOL_SCHEMAS],
    )

    def on_tool_start(tool_call_id: str, name: str, args: dict[str, Any]) -> None:
        tool_starts.append({"id": tool_call_id, "name": name, "args": normalize_tool_args(args)})

    def on_tool_complete(tool_call_id: str, name: str, args: dict[str, Any], result: Any) -> None:
        tool_completions.append(
            {
                "id": tool_call_id,
                "name": name,
                "args": normalize_tool_args(args),
                "result_preview": str(result)[:1000],
            }
        )

    api_mode = "codex_responses" if model.startswith("gpt-5") else "chat_completions"
    agent = AIAgent(
        base_url="https://api.openai.com/v1",
        api_key=os.environ["OPENAI_API_KEY"],
        provider="openai",
        api_mode=api_mode,
        model=model,
        max_iterations=max_iterations,
        enabled_toolsets=[TOOLSET_NAME],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        save_trajectories=False,
        ephemeral_system_prompt=build_system_prompt("Hermes Agent"),
        request_overrides={"temperature": temperature},
        tool_start_callback=on_tool_start,
        tool_complete_callback=on_tool_complete,
    )

    started = time.time()
    result = agent.run_conversation(build_user_prompt(scenario))
    elapsed_ms = int((time.time() - started) * 1000)
    calls = [call for call in mock.calls]
    payload = {
        "runtime": "hermes-agent",
        "scenario": scenario.name,
        "skill": scenario.skill,
        "model": model,
        "api_mode": api_mode,
        "elapsed_ms": elapsed_ms,
        "call_count": len(calls),
        "modes": [SIM.call_mode(call) for call in calls],
        "calls": calls,
        "tool_starts": tool_starts,
        "tool_completions": tool_completions,
        "final_response": result.get("final_response", ""),
        "status": "passed",
    }
    try:
        validate_live_calls(scenario, "hermes-agent", calls)
    except Exception as exc:
        payload["status"] = "failed"
        raise LiveRuntimeFailure(str(exc), payload) from exc
    return payload


def run_openclaw_scenario(
    scenario: Any,
    model: str,
    temperature: float,
    max_iterations: int,
) -> dict[str, Any]:
    del max_iterations
    if not OPENCLAW_ROOT.exists():
        raise RuntimeError(f"OpenClaw checkout missing: {OPENCLAW_ROOT}")
    load_openai_key()
    runner = ROOT / "scripts" / "openclaw_live_runtime_runner.mjs"
    if not runner.exists():
        raise RuntimeError(
            "OpenClaw live runner is not present yet. Run the Hermes runtime first or add "
            "scripts/openclaw_live_runtime_runner.mjs."
        )
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as result_file:
        result_path = Path(result_file.name)
    try:
        import subprocess

        env = os.environ.copy()
        env["SUPER_CARL_LIVE_RESULT_FILE"] = str(result_path)
        env["SUPER_CARL_LIVE_MODEL"] = model
        env["SUPER_CARL_LIVE_TEMPERATURE"] = str(temperature)
        env["SUPER_CARL_LIVE_SCENARIO"] = scenario.name
        env["SUPER_CARL_LIVE_SKILL"] = scenario.skill
        env["SUPER_CARL_LIVE_PROMPT"] = scenario.user_prompt
        env["SUPER_CARL_LIVE_SKILL_TEXT"] = skill_text(scenario)
        completed = subprocess.run(
            ["pnpm", "tsx", str(runner)],
            cwd=OPENCLAW_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=180,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "OpenClaw runner failed:\n"
                + completed.stdout[-2000:]
                + completed.stderr[-4000:]
            )
        payload = json.loads(result_path.read_text())
        calls = [normalize_tool_args(call) for call in payload.get("calls", [])]
        payload.update(
            {
                "runtime": "openclaw",
                "scenario": scenario.name,
                "skill": scenario.skill,
                "model": model,
                "call_count": len(calls),
                "modes": [SIM.call_mode(call) for call in calls],
                "calls": calls,
                "status": "passed",
            }
        )
        try:
            validate_live_calls(scenario, "openclaw", calls)
        except Exception as exc:
            payload["status"] = "failed"
            raise LiveRuntimeFailure(str(exc), payload) from exc
        return payload
    finally:
        try:
            result_path.unlink()
        except FileNotFoundError:
            pass


def print_table(results: list[dict[str, Any]], failures: list[dict[str, str]]) -> None:
    rows = [
        (
            result["runtime"],
            result["scenario"],
            result["skill"],
            str(result["call_count"]),
            ",".join(str(mode) for mode in result["modes"]),
            result["status"],
        )
        for result in results
    ]
    for failure in failures:
        partial = failure.get("partial") or {}
        rows.append(
            (
                failure["runtime"],
                failure["scenario"],
                failure.get("skill", ""),
                str(partial.get("call_count", 0)),
                ",".join(str(mode) for mode in partial.get("modes", [])),
                "failed",
            )
        )
    if not rows:
        return
    headers = ("runtime", "scenario", "skill", "calls", "modes", "status")
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def write_json(path: Path, results: list[dict[str, Any]], failures: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "results": results,
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run live stochastic Super Carl skill flows inside agent runtimes and "
            "compare emitted watch_signals traces to the contract."
        )
    )
    parser.add_argument(
        "--runtime",
        choices=("hermes-agent", "openclaw"),
        action="append",
        help="Runtime to execute. May be passed more than once. Defaults to hermes-agent.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="Scenario name to run. May be passed more than once. Defaults to a focused smoke set.",
    )
    parser.add_argument("--model", default=os.environ.get("SUPER_CARL_LIVE_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--json-out", type=Path, help="Optional file for full trace output.")
    parser.add_argument("--json", action="store_true", help="Print full JSON to stdout.")
    args = parser.parse_args()

    runtimes = args.runtime or ["hermes-agent"]
    scenarios = selected_scenarios(args.scenario)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    runners = {
        "hermes-agent": run_hermes_scenario,
        "openclaw": run_openclaw_scenario,
    }
    for runtime in runtimes:
        for scenario in scenarios:
            try:
                results.append(
                    runners[runtime](
                        scenario,
                        model=args.model,
                        temperature=args.temperature,
                        max_iterations=args.max_iterations,
                    )
                )
            except Exception as exc:
                partial = exc.partial if isinstance(exc, LiveRuntimeFailure) else {}
                failures.append(
                    {
                        "runtime": runtime,
                        "scenario": scenario.name,
                        "skill": scenario.skill,
                        "error": str(exc),
                        "partial": partial,
                    }
                )

    if args.json_out:
        write_json(args.json_out, results, failures)
    if args.json:
        print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    else:
        print_table(results, failures)
        if failures:
            print("\nFailures:")
            for failure in failures:
                print(f"- {failure['runtime']}/{failure['scenario']}: {failure['error']}")
        print(f"\nPassed {len(results)} live runtime flow(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
