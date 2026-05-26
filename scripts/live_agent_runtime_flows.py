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
    "competitor_engagement_icp_followup",
    "job_seeker_profile_matched_roles",
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


WATCH_SIGNALS_SCHEMA = {
    "name": "watch_signals",
    "description": (
        "Mock Super Carl MCP tool for Scan My Network watch projects. Use it to "
        "create or update durable watches, run checks, inspect hits/evidence, "
        "promote hits to reviewable project actions, and verify agent webhook delivery."
    ),
    "parameters": {
        "type": "object",
        "properties": {
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
            "sources": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
            },
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
        "required": ["mode"],
        "additionalProperties": True,
    },
}


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


class LiveMockWatchSignals(SIM.MockWatchSignals):
    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_tool_args(request)
        return super().call(normalized)


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

Use the `watch_signals` MCP tool whenever the user request involves configuring, running, inspecting, or delivering a Scan My Network watch. Do not answer only in prose when a tool call is needed.

Contract:
- Create or update a durable watch with `mode: "create"` or `mode: "update"` when the skill configures a watch.
- Use `project_id` when one is available.
- Use `hits` and then `evidence` before `promote_hit`.
- Every `evidence` call must include a concrete `signal_hit_id` from a prior
  `hits` result.
- When creating or updating a watch that can lead to outreach or project
  actions, include `action_policy.never_send_without_approval: true`.
- Never send outreach directly. `promote_hit` is not a send action; use it to
  prepare a reviewable project action or draft whenever the user asked for
  follow-up, outreach prep, intro prep, or next-action review.
- If the active skill says the flow is delivery/status-only or says not to
  promote hits, do not call `promote_hit`.
- Preserve `project_feed` when enabling `agent_webhook`.
- Carry role intent, source kinds, signal types, freshness policy, callback policy, and approval policy exactly when the skill calls for them.
""".strip()


def build_user_prompt(scenario: Any) -> str:
    return f"""
Load and follow this Super Carl skill:

<skill>
{skill_text(scenario)}
</skill>

User request:
{scenario.user_prompt}

Run the workflow now against the mock `watch_signals` MCP tool. If the workflow asks for a message, follow-up, intro request, or reviewed next action, call `promote_hit` after `evidence` with `draft_message: true`; this only queues a user-reviewable draft and does not send outreach. Stop after the watch/action setup and evidence-backed review are complete.
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

    mock = LiveMockWatchSignals(scenario.name, "hermes-agent")
    tool_starts: list[dict[str, Any]] = []
    tool_completions: list[dict[str, Any]] = []

    def handler(args: dict[str, Any], **_kwargs: Any) -> str:
        response = mock.call(args)
        return json.dumps(response, sort_keys=True)

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

    registry.register(
        name="watch_signals",
        toolset=TOOLSET_NAME,
        schema=WATCH_SIGNALS_SCHEMA,
        handler=handler,
        description=WATCH_SIGNALS_SCHEMA["description"],
        override=True,
    )
    create_custom_toolset(
        TOOLSET_NAME,
        "Live Super Carl runtime validation toolset with a mocked watch_signals MCP surface.",
        tools=["watch_signals"],
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
        "modes": [call.get("mode") for call in calls],
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
                "modes": [call.get("mode") for call in calls],
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
