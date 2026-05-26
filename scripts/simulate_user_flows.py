#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
AGENT_RUNTIMES = ("openclaw", "hermes-agent")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter")
    match = re.search(r"\n---\s*\n", text[4:])
    if not match:
        raise ValueError("missing closing frontmatter")
    raw = text[4 : match.start() + 4]
    body = text[match.end() + 4 :]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data, body


def load_skill_names() -> set[str]:
    names: set[str] = set()
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        frontmatter, _ = parse_frontmatter(skill_md.read_text())
        name = frontmatter.get("name")
        if not name:
            raise ValueError(f"{skill_md.relative_to(ROOT)} missing name")
        names.add(name)
    return names


@dataclass(frozen=True)
class Scenario:
    name: str
    skill: str
    user_prompt: str
    calls: list[dict[str, Any]]
    expected_source_kinds: tuple[str, ...]
    expected_signal_types: tuple[str, ...]
    expected_role_intent: str | None = None
    expect_create_or_update: bool = True
    expect_promote: bool = True
    expect_webhook: bool = False
    expect_freshness_policy: bool = False


class MockWatchSignals:
    def __init__(self, scenario_name: str, runtime: str) -> None:
        self.scenario_name = scenario_name
        self.runtime = runtime
        self.calls: list[dict[str, Any]] = []
        self.project_id = f"project_{scenario_name}_{runtime.replace('-', '_')}"
        self.watch_config_id = f"watch_{scenario_name}_{runtime.replace('-', '_')}"
        self.hit_id = f"hit_{scenario_name}_{runtime.replace('-', '_')}_1"

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        req = deepcopy(request)
        req.setdefault("project_id", self.project_id)
        mode = req.get("mode")
        if not mode:
            raise ValueError("watch_signals call missing mode")
        self.calls.append(req)

        if mode == "role_packs":
            return {
                "role_packs": [
                    "gtm",
                    "founder",
                    "sales",
                    "job_seeker",
                    "recruiter",
                    "networking",
                ]
            }
        if mode in {"create", "update"}:
            return {
                "project_id": req["project_id"],
                "watch_config_id": req.get("watch_config_id", self.watch_config_id),
                "status": "active",
                "delivery_channels": req.get("delivery_channels", ["project_feed"]),
                "credits": {
                    "estimated_preview_searches_per_run": req.get(
                        "estimated_preview_searches_per_run", 3
                    )
                },
            }
        if mode == "run_now":
            return {
                "project_id": req["project_id"],
                "watch_config_id": req.get("watch_config_id", self.watch_config_id),
                "run_id": f"run_{self.scenario_name}_{self.runtime.replace('-', '_')}",
                "status": "completed",
            }
        if mode == "hits":
            return {
                "hits": [
                    {
                        "signal_hit_id": self.hit_id,
                        "score": 0.91,
                        "match_reasons": [
                            "ICP fit",
                            "recent signal",
                            "social proximity path available",
                        ],
                        "evidence_citations": [
                            {
                                "kind": "post_or_profile",
                                "title": "Recent relevant signal",
                                "url": "https://example.com/evidence",
                            }
                        ],
                    }
                ]
            }
        if mode == "evidence":
            return {
                "signal_hit_id": req.get("signal_hit_id", self.hit_id),
                "citations": [
                    {
                        "kind": "profile_or_post",
                        "snippet": "Inspectable evidence supporting the signal.",
                        "url": "https://example.com/evidence",
                    },
                    {
                        "kind": "social_proximity",
                        "snippet": "Warm path through a known relationship.",
                    },
                ],
                "recipient_context": {
                    "receptivity": "medium_high",
                    "recommended_opener": "Lead with the cited evidence and useful context.",
                },
            }
        if mode == "promote_hit":
            return {
                "signal_hit_id": req.get("signal_hit_id", self.hit_id),
                "project_action": {
                    "routed": True,
                    "approval_required": True,
                    "draft_message": bool(req.get("draft_message")),
                },
            }
        if mode == "delivery_status":
            return {
                "project_id": req["project_id"],
                "channels": [
                    {
                        "channel": "project_feed",
                        "status": "delivered",
                        "event_type": "digest_ready",
                    },
                    {
                        "channel": "agent_webhook",
                        "status": "delivered",
                        "event_type": "signal_hit",
                    },
                ],
            }
        if mode in {"status", "pause", "resume", "dismiss_hit", "snooze_hit"}:
            return {"project_id": req["project_id"], "status": "ok"}
        raise ValueError(f"unsupported watch_signals mode: {mode}")


SCENARIOS: list[Scenario] = [
    Scenario(
        name="account_intent_daily_digest",
        skill="super-carl-account-intent-watch",
        user_prompt=(
            "Watch my spreadsheet of target accounts for GTM hiring, leadership moves, "
            "category posts, and warm paths. Send a daily report only when something changed."
        ),
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Target account intent watch",
                "role_intent": "gtm",
                "source_kind": "spreadsheet",
                "sources": [
                    {
                        "source_kind": "spreadsheet",
                        "url": "https://docs.google.com/spreadsheets/d/example",
                        "label": "Target accounts",
                    }
                ],
                "watch_prompt": "Watch target accounts for timing signals and warm paths.",
                "signal_types": [
                    "hiring_spike",
                    "company_growth",
                    "posts",
                    "role_change",
                    "warm_intro",
                ],
                "delivery_channels": ["project_feed", "app_push", "email_digest"],
                "action_policy": {
                    "default_action": "add_to_review_queue",
                    "never_send_without_approval": True,
                },
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_message"],
            },
        ],
        expected_source_kinds=("spreadsheet",),
        expected_signal_types=(
            "hiring_spike",
            "company_growth",
            "posts",
            "role_change",
            "warm_intro",
        ),
        expected_role_intent="gtm",
    ),
    Scenario(
        name="competitor_engagement_icp_followup",
        skill="super-carl-competitor-engagement-watch",
        user_prompt=(
            "Look over my market for people liking or commenting on competitor posts "
            "about outbound quality. Choose top ICPs and prepare value-led follow-up."
        ),
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Competitor engagement radar",
                "role_intent": "sales",
                "source_kind": "competitor_set",
                "sources": [
                    {"source_kind": "competitor_set", "value": "Competitor A; Competitor B"},
                    {
                        "source_kind": "freeform_scope",
                        "value": "VP Sales and RevOps leaders at B2B SaaS companies",
                    },
                ],
                "watch_prompt": (
                    "Find people engaging with competitor posts, rank top ICP-fit people, "
                    "and include warm intro paths."
                ),
                "signal_types": ["competitor_engagement", "posts", "warm_intro"],
                "delivery_channels": ["project_feed", "email_digest"],
                "action_policy": {
                    "default_action": "draft_message",
                    "never_send_without_approval": True,
                },
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_message"],
            },
        ],
        expected_source_kinds=("competitor_set",),
        expected_signal_types=("competitor_engagement", "posts", "warm_intro"),
        expected_role_intent="sales",
    ),
    Scenario(
        name="owned_audience_post_engagement",
        skill="super-carl-owned-audience-follow-up",
        user_prompt=(
            "Watch people who like my posts about GTM monitoring and social proximity. "
            "Tell me who is worth following up with and why."
        ),
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Owned audience follow-up",
                "role_intent": "founder",
                "source_kind": "owner_posts",
                "sources": [
                    {
                        "source_kind": "owner_posts",
                        "value": "Posts about GTM monitoring and social proximity",
                    },
                    {
                        "source_kind": "network_scope",
                        "value": "1st and 2nd degree reachable paths",
                    },
                ],
                "watch_prompt": "Watch engagement on my posts and find useful follow-ups.",
                "signal_types": ["liked_my_post", "follow_up", "warm_intro"],
                "delivery_channels": ["project_feed", "app_push", "email_digest"],
                "action_policy": {
                    "default_action": "add_to_review_queue",
                    "never_send_without_approval": True,
                },
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_message"],
            },
        ],
        expected_source_kinds=("owner_posts", "network_scope"),
        expected_signal_types=("liked_my_post", "follow_up", "warm_intro"),
        expected_role_intent="founder",
    ),
    Scenario(
        name="job_seeker_profile_matched_roles",
        skill="super-carl-job-seeker-opportunity-watch",
        user_prompt=(
            "Use my profile to monitor senior product roles in developer tools, "
            "new recruiter posts, hiring managers, and warm intro paths."
        ),
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Senior product roles worth applying to",
                "role_intent": "job_seeker",
                "source_kind": "owner_profile",
                "sources": [
                    {
                        "source_kind": "owner_profile",
                        "value": "Use my Super Carl profile and work history",
                    },
                    {
                        "source_kind": "account_list",
                        "value": "AI infrastructure, developer tools, and data platforms",
                    },
                    {
                        "source_kind": "job_search",
                        "value": "Senior product roles, remote or Bay Area",
                    },
                    {
                        "source_kind": "network_scope",
                        "value": "Hiring managers, recruiters, alumni, and coworkers",
                    },
                ],
                "watch_prompt": "Find new senior product roles that fit my profile.",
                "signal_types": ["jobs", "employee_post", "company_growth", "warm_intro"],
                "delivery_channels": ["project_feed", "email_digest"],
                "action_policy": {
                    "default_action": "draft_intro_request",
                    "never_send_without_approval": True,
                },
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_intro_request"],
            },
        ],
        expected_source_kinds=("owner_profile", "job_search", "network_scope"),
        expected_signal_types=("jobs", "employee_post", "company_growth", "warm_intro"),
        expected_role_intent="job_seeker",
    ),
    Scenario(
        name="recruiter_candidate_radar",
        skill="super-carl-recruiter-candidate-radar",
        user_prompt=(
            "Watch this candidate spreadsheet and competitor alumni list for role changes, "
            "technical posts, and team warm paths for a founding AI engineer search."
        ),
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Founding AI engineer candidate radar",
                "role_intent": "recruiter",
                "source_kind": "spreadsheet",
                "sources": [
                    {
                        "source_kind": "spreadsheet",
                        "url": "https://docs.google.com/spreadsheets/d/example",
                        "label": "Candidate and competitor source list",
                    },
                    {"source_kind": "people_list", "value": "Known AI infra candidates"},
                    {
                        "source_kind": "network_scope",
                        "value": "Team warm paths and prior coworkers",
                    },
                ],
                "watch_prompt": "Rank high-fit candidates and cite the source row and warm path.",
                "signal_types": ["role_change", "employee_post", "posts", "warm_intro"],
                "delivery_channels": ["project_feed", "email_digest"],
                "action_policy": {
                    "default_action": "draft_message",
                    "never_send_without_approval": True,
                },
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_message"],
            },
        ],
        expected_source_kinds=("spreadsheet", "people_list", "network_scope"),
        expected_signal_types=("role_change", "employee_post", "posts", "warm_intro"),
        expected_role_intent="recruiter",
    ),
    Scenario(
        name="champion_mover_weekly_profile_updates",
        skill="super-carl-champion-mover",
        user_prompt=(
            "Watch former customers, advisors, and coworkers for role changes. "
            "Use weekly profile update cadence and prepare relationship-aware follow-ups."
        ),
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Champion mover watch",
                "role_intent": "networking",
                "source_kind": "people_list",
                "sources": [
                    {
                        "source_kind": "people_list",
                        "value": "Former customers, advisors, and coworkers",
                    },
                    {
                        "source_kind": "network_scope",
                        "value": "Use social proximity and prior relationship evidence",
                    },
                ],
                "watch_prompt": "Surface relationship-aware role-change follow-ups.",
                "signal_types": ["role_change", "follow_up", "warm_intro"],
                "delivery_channels": ["project_feed", "app_push", "email_digest"],
                "freshness_policy": {
                    "profile_updates": "weekly_or_when_new_bulk_ingest_arrives"
                },
                "action_policy": {
                    "default_action": "draft_message",
                    "never_send_without_approval": True,
                },
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_message"],
            },
        ],
        expected_source_kinds=("people_list", "network_scope"),
        expected_signal_types=("role_change", "follow_up", "warm_intro"),
        expected_role_intent="networking",
        expect_freshness_policy=True,
    ),
    Scenario(
        name="warm_intro_review_existing_hits",
        skill="super-carl-warm-intro-outreach",
        user_prompt=(
            "Look at this project's current hits, tell me who has the best warm path, "
            "and prepare a reviewed draft for the top one."
        ),
        calls=[
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {
                "mode": "promote_hit",
                "signal_hit_id": "SCENARIO_HIT",
                "draft_message": True,
                "actions": ["draft_message"],
            },
        ],
        expected_source_kinds=(),
        expected_signal_types=(),
        expect_create_or_update=False,
    ),
    Scenario(
        name="agent_webhook_digest_delivery",
        skill="super-carl-agent-webhook-digests",
        user_prompt=(
            "Configure my OpenClaw callback for this Super Carl project, keep the project "
            "feed on, and verify whether digest and signal-hit callbacks are delivered."
        ),
        calls=[
            {
                "mode": "update",
                "watch_config_id": "watch_existing",
                "delivery_channels": ["project_feed", "agent_webhook", "email_digest"],
                "callback_policy": {
                    "callback_id": "openclaw-prod",
                    "mcp_connection_id": "mcp_connection_123",
                    "event_types": ["signal_hit", "digest_ready", "draft_ready"],
                    "delegate_routing": "allow_team_sub_users",
                },
            },
            {"mode": "delivery_status"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
        ],
        expected_source_kinds=(),
        expected_signal_types=(),
        expect_promote=False,
        expect_webhook=True,
    ),
]


def resolve_hit_placeholder(call: dict[str, Any], hit_id: str) -> dict[str, Any]:
    resolved = deepcopy(call)
    if resolved.get("signal_hit_id") == "SCENARIO_HIT":
        resolved["signal_hit_id"] = hit_id
    return resolved


def source_kinds_from(call: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    source_kind = call.get("source_kind")
    if source_kind:
        kinds.add(str(source_kind))
    for source in call.get("sources", []):
        if isinstance(source, dict) and source.get("source_kind"):
            kinds.add(str(source["source_kind"]))
    return kinds


def assert_scenario(scenario: Scenario, runtime: str, calls: list[dict[str, Any]]) -> None:
    modes = [call.get("mode") for call in calls]
    create_or_update = [call for call in calls if call.get("mode") in {"create", "update"}]

    if scenario.expect_create_or_update and not create_or_update:
        raise AssertionError("expected create or update call")
    if not scenario.expect_create_or_update and create_or_update:
        raise AssertionError("did not expect create/update for review-only flow")

    if scenario.expect_promote and "promote_hit" not in modes:
        raise AssertionError("expected promote_hit call")
    if not scenario.expect_promote and "promote_hit" in modes:
        raise AssertionError("did not expect promote_hit call")

    if "promote_hit" in modes:
        first_evidence = modes.index("evidence") if "evidence" in modes else -1
        first_promote = modes.index("promote_hit")
        if first_evidence == -1 or first_evidence > first_promote:
            raise AssertionError("promote_hit must happen after evidence")

    if "send" in modes or "send_message" in modes or "send_email" in modes:
        raise AssertionError("skills must not send directly")

    for call in create_or_update:
        action_policy = call.get("action_policy", {})
        if scenario.skill != "super-carl-agent-webhook-digests":
            if action_policy.get("never_send_without_approval") is not True:
                raise AssertionError("create/update must require approval before sending")
        if scenario.expected_role_intent and call.get("role_intent") != scenario.expected_role_intent:
            raise AssertionError(
                f"expected role_intent {scenario.expected_role_intent}, got {call.get('role_intent')}"
            )
        missing_sources = set(scenario.expected_source_kinds) - source_kinds_from(call)
        if missing_sources:
            raise AssertionError(f"missing source kinds: {sorted(missing_sources)}")
        missing_signals = set(scenario.expected_signal_types) - set(call.get("signal_types", []))
        if missing_signals:
            raise AssertionError(f"missing signal types: {sorted(missing_signals)}")

    if scenario.expect_webhook:
        webhook_call = create_or_update[0] if create_or_update else {}
        channels = set(webhook_call.get("delivery_channels", []))
        if "agent_webhook" not in channels:
            raise AssertionError("agent webhook flow must enable agent_webhook")
        if "project_feed" not in channels:
            raise AssertionError("agent webhook flow must keep project_feed enabled")
        callback_policy = webhook_call.get("callback_policy")
        if not isinstance(callback_policy, dict) or not callback_policy.get("mcp_connection_id"):
            raise AssertionError("agent webhook flow must include callback_policy")
        if "delivery_status" not in modes:
            raise AssertionError("agent webhook flow must verify delivery_status")

    if scenario.expect_freshness_policy:
        freshness_call = create_or_update[0] if create_or_update else {}
        profile_freshness = freshness_call.get("freshness_policy", {}).get("profile_updates")
        if profile_freshness != "weekly_or_when_new_bulk_ingest_arrives":
            raise AssertionError("profile update watch must carry weekly ingest freshness policy")

    for evidence_call in [call for call in calls if call.get("mode") == "evidence"]:
        if not evidence_call.get("signal_hit_id"):
            raise AssertionError("evidence calls must target a signal_hit_id")

    for promote_call in [call for call in calls if call.get("mode") == "promote_hit"]:
        if promote_call.get("draft_message") is not True:
            raise AssertionError("promote_hit should request a reviewable draft")


def run_scenario(scenario: Scenario, runtime: str) -> dict[str, Any]:
    skill_names = load_skill_names()
    if scenario.skill not in skill_names:
        raise AssertionError(f"missing skill folder for {scenario.skill}")

    mock = MockWatchSignals(scenario.name, runtime)
    outputs: list[dict[str, Any]] = []
    for call in scenario.calls:
        resolved = resolve_hit_placeholder(call, mock.hit_id)
        outputs.append(mock.call(resolved))

    assert_scenario(scenario, runtime, mock.calls)
    return {
        "scenario": scenario.name,
        "runtime": runtime,
        "skill": scenario.skill,
        "user_prompt": scenario.user_prompt,
        "call_count": len(mock.calls),
        "modes": [call["mode"] for call in mock.calls],
        "project_id": mock.project_id,
        "watch_config_id": mock.watch_config_id,
        "outputs": outputs,
        "status": "passed",
    }


def print_table(results: list[dict[str, Any]]) -> None:
    headers = ("scenario", "runtime", "skill", "calls", "modes")
    rows = [
        (
            result["scenario"],
            result["runtime"],
            result["skill"],
            str(result["call_count"]),
            ",".join(result["modes"]),
        )
        for result in results
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    print(f"\nPassed {len(results)} simulated agent flows")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic Super Carl agent skill user-flow simulations."
    )
    parser.add_argument(
        "--runtime",
        choices=AGENT_RUNTIMES,
        action="append",
        help="Runtime to simulate. May be passed more than once. Defaults to both.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="Scenario name to run. May be passed more than once. Defaults to all.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON results.")
    args = parser.parse_args()

    selected_runtimes = tuple(args.runtime or AGENT_RUNTIMES)
    selected_scenarios = set(args.scenario or [scenario.name for scenario in SCENARIOS])
    unknown = selected_scenarios - {scenario.name for scenario in SCENARIOS}
    if unknown:
        print(f"Unknown scenario(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for scenario in SCENARIOS:
        if scenario.name not in selected_scenarios:
            continue
        for runtime in selected_runtimes:
            try:
                results.append(run_scenario(scenario, runtime))
            except Exception as exc:
                failures.append(f"{runtime}/{scenario.name}: {exc}")

    if args.json:
        print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    else:
        if results:
            print_table(results)
        if failures:
            print("\nFailures:", file=sys.stderr)
            print("\n".join(failures), file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
