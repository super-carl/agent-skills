#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
AGENT_RUNTIMES = ("openclaw", "hermes-agent")

WATCH_MUTATING_MODES = {"create", "update", "promote_hit", "pause", "resume", "dismiss_hit", "snooze_hit"}
PROJECT_MUTATING_MODES = {
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
}


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
    expected_tools: tuple[str, ...] = ("watch_signals",)
    expected_source_kinds: tuple[str, ...] = ()
    expected_signal_types: tuple[str, ...] = ()
    expected_role_intent: str | None = None
    expect_create_or_update: bool = False
    expect_promote: bool = False
    expect_webhook: bool = False
    expect_freshness_policy: bool = False
    expect_agent_session: bool = False
    expect_project_binding: bool = False
    expect_project_grouping: bool = False
    expect_project_message_generation: bool = False
    expect_send_draft: bool = False
    expect_explicit_send: bool = False
    expect_with_people_tools: tuple[str, ...] = field(default_factory=tuple)


class MockSuperCarlMCP:
    def __init__(self, scenario_name: str, runtime: str) -> None:
        suffix = f"{scenario_name}_{runtime.replace('-', '_')}"
        self.scenario_name = scenario_name
        self.runtime = runtime
        self.calls: list[dict[str, Any]] = []
        self.agent_session_id = f"session_{suffix}"
        self.project_id = f"project_{suffix}"
        self.watch_config_id = f"watch_{suffix}"
        self.hit_id = f"hit_{suffix}_1"
        self.person_ids = [f"person_{suffix}_{index}" for index in range(1, 5)]
        self.project_target_ids = [f"target_{suffix}_{index}" for index in range(1, 5)]
        self.job_id = f"job_{suffix}_1"
        self.company_id = f"company_{suffix}_1"
        self.post_id = f"post_{suffix}_1"

    def call(self, tool: str, request: dict[str, Any]) -> dict[str, Any]:
        req = deepcopy(request)
        if tool == "watch_signals":
            req.setdefault("project_id", self.project_id)
        mode = req.get("mode")
        if tool in {"watch_signals", "agent_session", "project_action", "send_communication"} and not mode:
            raise ValueError(f"{tool} call missing mode")
        self.calls.append({"tool": tool, **req})

        if tool == "agent_session":
            return self._agent_session(req)
        if tool == "people_search":
            return self._people_search(req)
        if tool == "company_search":
            return self._company_search(req)
        if tool == "jobs_search":
            return self._jobs_search(req)
        if tool == "posts_search":
            return self._posts_search(req)
        if tool == "people_lookup_batch":
            return self._people_lookup_batch(req)
        if tool == "social_proximity_research":
            return self._social_proximity_research(req)
        if tool == "project_action":
            return self._project_action(req)
        if tool == "send_communication":
            return self._send_communication(req)
        if tool == "watch_signals":
            return self._watch_signals(req)
        raise ValueError(f"unsupported tool: {tool}")

    def _agent_session(self, req: dict[str, Any]) -> dict[str, Any]:
        mode = req["mode"]
        if mode == "start":
            return {
                "success": True,
                "agent_session_id": self.agent_session_id,
                "session_binding": {"status": "started", "agent_session_id": self.agent_session_id},
            }
        if mode in {"bind", "switch_project", "status"}:
            return {
                "success": True,
                "agent_session_id": req.get("agent_session_id", self.agent_session_id),
                "project_id": req.get("project_id", self.project_id),
                "session_binding": {
                    "status": "bound",
                    "agent_session_id": req.get("agent_session_id", self.agent_session_id),
                    "project_id": req.get("project_id", self.project_id),
                },
            }
        if mode in {"list", "close"}:
            return {"success": True, "agent_session_id": self.agent_session_id}
        raise ValueError(f"unsupported agent_session mode: {mode}")

    def _people_search(self, req: dict[str, Any]) -> dict[str, Any]:
        query = str(req.get("query", "")).lower()
        if "revops" in query or "vp sales" in query or req.get("role_intent") == "sales":
            headline = "VP Sales at ExampleCo"
        elif "hiring manager" in query or req.get("role_intent") == "job_seeker":
            headline = "VP Engineering at ExampleCo"
        else:
            headline = "VP Engineering at ExampleCo"
        return {
            "search_id": f"people_search_{self.scenario_name}",
            "users": [
                {
                    "id": person_id,
                    "name": f"Candidate {index}",
                    "headline": headline,
                    "match_reasons": ["role fit", "company fit", "social proximity"],
                    "evidence_citations": [
                        {"kind": "profile", "snippet": "Current role and company match the query."}
                    ],
                    "relationship": {"social_proximity_score": 0.78},
                }
                for index, person_id in enumerate(self.person_ids[:3], start=1)
            ],
            "next_actions": [
                {"id": "people_search.run_review", "tool": "people_search"},
                {"id": "social_proximity_research.start", "tool": "social_proximity_research"},
            ],
        }

    def _company_search(self, req: dict[str, Any]) -> dict[str, Any]:
        return {
            "search_id": f"company_search_{self.scenario_name}",
            "companies": [{"id": self.company_id, "name": "ExampleCo", "fit": "AI infrastructure"}],
            "next_actions": [{"id": "people_search.bind_company", "tool": "people_search"}],
        }

    def _jobs_search(self, req: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "search_id": f"jobs_search_{self.scenario_name}",
            "jobs": [
                {
                    "id": self.job_id,
                    "title": "VP Engineering",
                    "company_id": self.company_id,
                    "company_name": "ExampleCo",
                    "fit_reasons": ["engineering leadership", "AI infrastructure", "startup stage"],
                    "evidence_citations": [{"kind": "job", "snippet": "Role requirements match profile."}],
                }
            ],
            "next_actions": [{"id": "people_search.bind_job_company", "tool": "people_search"}],
        }
        if req.get("with_people"):
            payload["people_by_company"] = {
                self.company_id: [
                    {
                        "id": self.person_ids[0],
                        "name": "Engineering Leader",
                        "path": "hiring manager or leadership path",
                    }
                ]
            }
        return payload

    def _posts_search(self, req: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "search_id": f"posts_search_{self.scenario_name}",
            "posts": [
                {
                    "id": self.post_id,
                    "url": "https://example.com/post",
                    "snippet": "Competitor discussion about GTM monitoring.",
                    "engagement": [{"person_id": self.person_ids[0], "type": "comment"}],
                }
            ],
            "people_search_binding": {"source_tool": "posts_search", "post_ids": [self.post_id]},
            "next_actions": [{"id": "people_search.from_posts", "tool": "people_search"}],
        }
        if req.get("with_people"):
            payload["people"] = [{"id": self.person_ids[0], "name": "Engaged ICP"}]
        return payload

    def _people_lookup_batch(self, req: dict[str, Any]) -> dict[str, Any]:
        return {
            "profiles": [
                {
                    "id": self.person_ids[0],
                    "relationship": {
                        "social_map": {
                            "entries": [
                                {
                                    "path_type": "confirmed_mutual",
                                    "connector": "Known Connector",
                                    "evidence": "Shared prior employer",
                                }
                            ]
                        }
                    },
                }
            ]
        }

    def _social_proximity_research(self, req: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_user_id": req.get("target_user_id", self.person_ids[0]),
            "status": "completed",
            "paths": [{"connector_user_id": self.person_ids[2], "strength": "warm"}],
        }

    def _project_action(self, req: dict[str, Any]) -> dict[str, Any]:
        mode = req["mode"]
        project_id = req.get("project_id", self.project_id)
        if mode == "add_targets":
            ids = req.get("target_user_ids") or ([req["target_user_id"]] if req.get("target_user_id") else [])
            return {
                "project_id": project_id,
                "current_session_project_id": project_id,
                "added_count": len(ids),
                "targets": [
                    {"project_target_id": self.project_target_ids[index], "target_user_id": target_id}
                    for index, target_id in enumerate(ids[: len(self.project_target_ids)])
                ],
            }
        if mode == "targets":
            return {
                "project_id": project_id,
                "targets": [
                    {
                        "project_target_id": self.project_target_ids[0],
                        "target_user_id": self.person_ids[0],
                        "outreach_status": "pending",
                        "reviewed_message": "The exact reviewed message the user approved.",
                        "message": "The exact reviewed message the user approved.",
                        "channel": "linkedin_send_message",
                        "evidence": [{"kind": "profile", "snippet": "Evidence supports outreach."}],
                    }
                ],
            }
        if mode == "generate_messages":
            return {
                "project_id": project_id,
                "generated_count": 2,
                "drafts": [
                    {
                        "project_target_id": self.project_target_ids[0],
                        "message": "Personalized draft using cited evidence.",
                    }
                ],
            }
        if mode == "update_message":
            return {
                "project_id": project_id,
                "project_target_id": req.get("project_target_id", self.project_target_ids[0]),
                "saved": True,
                "review_action": req.get("review_action", "save"),
            }
        if mode == "send_readiness":
            return {"project_id": project_id, "ready_count": 2, "not_previewed_count": 0}
        if mode in {"list", "status", "metrics", "recipient_emails"}:
            return {"project_id": project_id, "status": "ok"}
        if mode in PROJECT_MUTATING_MODES:
            return {"project_id": project_id, "status": "ok"}
        raise ValueError(f"unsupported project_action mode: {mode}")

    def _send_communication(self, req: dict[str, Any]) -> dict[str, Any]:
        mode = req["mode"]
        if mode == "precheck":
            return {
                "target_user_id": req.get("target_user_id", self.person_ids[0]),
                "channels": [
                    {"channel": "gmail_send", "available": True},
                    {"channel": "linkedin_send_message", "available": True},
                    {"channel": "supercarl_referral_request", "available": True},
                ],
            }
        if mode == "history":
            return {
                "target_user_id": req.get("target_user_id", self.person_ids[0]),
                "entries": [],
                "next_actions": [
                    {
                        "id": "people_lookup_batch.outreach_context",
                        "tool": "people_lookup_batch",
                        "args": {"relationship_detail": "intro_paths"},
                    }
                ],
            }
        if mode == "draft":
            return {
                "target_user_id": req.get("target_user_id", self.person_ids[0]),
                "draft": {"channel": req.get("channel", "linkedin_send_message"), "message": req.get("message", "")},
                "sent": False,
            }
        if mode in {"status", "cancel"}:
            return {"status": "ok"}
        if mode == "send":
            return {"status": "sent"}
        raise ValueError(f"unsupported send_communication mode: {mode}")

    def _watch_signals(self, req: dict[str, Any]) -> dict[str, Any]:
        mode = req["mode"]
        if mode == "role_packs":
            return {"role_packs": ["gtm", "founder", "sales", "job_seeker", "recruiter", "networking"]}
        if mode in {"create", "update"}:
            return {
                "project_id": req["project_id"],
                "watch_config_id": req.get("watch_config_id", self.watch_config_id),
                "status": "active",
                "delivery_channels": req.get("delivery_channels", ["project_feed"]),
                "credits": {"estimated_preview_searches_per_run": req.get("estimated_preview_searches_per_run", 3)},
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
                        "match_reasons": ["ICP fit", "recent signal", "social proximity path available"],
                        "evidence_citations": [
                            {"kind": "post_or_profile", "title": "Recent relevant signal", "url": "https://example.com/evidence"}
                        ],
                    }
                ]
            }
        if mode == "evidence":
            return {
                "signal_hit_id": req.get("signal_hit_id", self.hit_id),
                "citations": [
                    {"kind": "profile_or_post", "snippet": "Inspectable evidence supporting the signal.", "url": "https://example.com/evidence"},
                    {"kind": "social_proximity", "snippet": "Warm path through a known relationship."},
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
                    {"channel": "project_feed", "status": "delivered", "event_type": "digest_ready"},
                    {"channel": "agent_webhook", "status": "delivered", "event_type": "signal_hit"},
                ],
            }
        if mode in {"status", "pause", "resume", "dismiss_hit", "snooze_hit"}:
            return {"project_id": req["project_id"], "status": "ok"}
        raise ValueError(f"unsupported watch_signals mode: {mode}")


def source_kinds_from(call: dict[str, Any]) -> set[str]:
    kinds: set[str] = set()
    source_kind = call.get("source_kind")
    if source_kind:
        kinds.add(str(source_kind))
    for source in call.get("sources", []):
        if isinstance(source, dict) and source.get("source_kind"):
            kinds.add(str(source["source_kind"]))
    return kinds


def resolve_placeholders(value: Any, mock: MockSuperCarlMCP) -> Any:
    if isinstance(value, str):
        return {
            "SCENARIO_HIT": mock.hit_id,
            "SCENARIO_AGENT_SESSION": mock.agent_session_id,
            "SCENARIO_PROJECT": mock.project_id,
            "SCENARIO_PERSON_1": mock.person_ids[0],
            "SCENARIO_PERSON_2": mock.person_ids[1],
            "SCENARIO_PERSON_3": mock.person_ids[2],
            "SCENARIO_PROJECT_TARGET_1": mock.project_target_ids[0],
            "SCENARIO_JOB_1": mock.job_id,
            "SCENARIO_COMPANY_1": mock.company_id,
            "SCENARIO_POST_1": mock.post_id,
        }.get(value, value)
    if isinstance(value, list):
        return [resolve_placeholders(item, mock) for item in value]
    if isinstance(value, dict):
        return {key: resolve_placeholders(item, mock) for key, item in value.items()}
    return value


def call_mode(call: dict[str, Any]) -> str:
    mode = call.get("mode")
    return f"{call.get('tool')}.{mode}" if mode else str(call.get("tool"))


def assert_watch_contract(scenario: Scenario, calls: list[dict[str, Any]]) -> None:
    watch_calls = [call for call in calls if call.get("tool") == "watch_signals"]
    if "watch_signals" not in scenario.expected_tools:
        if watch_calls:
            raise AssertionError("direct-only flow unexpectedly called watch_signals")
        return

    modes = [call.get("mode") for call in watch_calls]
    create_or_update = [call for call in watch_calls if call.get("mode") in {"create", "update"}]

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

    for call in create_or_update:
        action_policy = call.get("action_policy", {})
        if scenario.skill != "super-carl-agent-webhook-digests":
            if action_policy.get("never_send_without_approval") is not True:
                raise AssertionError("create/update must require approval before sending")
        if scenario.expected_role_intent and call.get("role_intent") != scenario.expected_role_intent:
            raise AssertionError(f"expected role_intent {scenario.expected_role_intent}, got {call.get('role_intent')}")
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

    for evidence_call in [call for call in watch_calls if call.get("mode") == "evidence"]:
        if not evidence_call.get("signal_hit_id"):
            raise AssertionError("evidence calls must target a signal_hit_id")

    for promote_call in [call for call in watch_calls if call.get("mode") == "promote_hit"]:
        if promote_call.get("draft_message") is not True:
            raise AssertionError("promote_hit should request a reviewable draft")


def assert_direct_contract(scenario: Scenario, calls: list[dict[str, Any]]) -> None:
    tools = [call.get("tool") for call in calls]
    for tool in scenario.expected_tools:
        if tool not in tools:
            raise AssertionError(f"expected tool call: {tool}")

    direct_calls = [call for call in calls if call.get("tool") != "watch_signals"]
    if not direct_calls:
        return

    if scenario.expect_agent_session:
        first = direct_calls[0]
        if first.get("tool") != "agent_session" or first.get("mode") not in {"start", "list", "status"}:
            raise AssertionError("direct flows must start by starting, listing, or checking an agent_session")

        for call in direct_calls[1:]:
            if call.get("tool") == "agent_session" and call.get("mode") in {"list", "start"}:
                continue
            if call.get("tool") == "project_action" and call.get("mode") == "list":
                continue
            if call.get("tool") != "agent_session" and not call.get("agent_session_id"):
                raise AssertionError(f"{call.get('tool')} call missing agent_session_id")
            if call.get("tool") == "agent_session" and call.get("mode") != "list" and not call.get("agent_session_id"):
                raise AssertionError("agent_session follow-up call missing agent_session_id")

    if scenario.expect_project_binding:
        project_binding = any(
            (call.get("tool") == "agent_session" and call.get("mode") == "switch_project")
            or (call.get("tool") == "project_action" and call.get("mode") in {"add_targets", "targets", "generate_messages", "update_message"})
            for call in direct_calls
        )
        if not project_binding:
            raise AssertionError("direct flow must bind to or create/use a project")

    if scenario.expect_project_grouping:
        add_targets = [call for call in direct_calls if call.get("tool") == "project_action" and call.get("mode") == "add_targets"]
        if not add_targets:
            raise AssertionError("expected project_action add_targets")
        if not any(len(call.get("target_user_ids", [])) > 0 or call.get("target_user_id") for call in add_targets):
            raise AssertionError("add_targets must include target ids")

    for call in direct_calls:
        if call.get("tool") == "project_action" and call.get("mode") in PROJECT_MUTATING_MODES:
            if call.get("user_confirmed") is not True:
                raise AssertionError(f"project_action {call.get('mode')} must pass user_confirmed=true")

    if scenario.expect_project_message_generation:
        modes = [call_mode(call) for call in direct_calls]
        if "project_action.generate_messages" not in modes:
            raise AssertionError("expected grouped project message generation")
        if "project_action.add_targets" in modes and modes.index("project_action.generate_messages") < modes.index("project_action.add_targets"):
            raise AssertionError("generate_messages must happen after add_targets")

    if scenario.expect_send_draft:
        modes = [call_mode(call) for call in direct_calls]
        for required in ("send_communication.precheck", "send_communication.history", "send_communication.draft"):
            if required not in modes:
                raise AssertionError(f"expected {required}")
        if not (modes.index("send_communication.precheck") < modes.index("send_communication.history") < modes.index("send_communication.draft")):
            raise AssertionError("send_communication draft flow must be precheck -> history -> draft")

    send_calls = [call for call in direct_calls if call.get("tool") == "send_communication" and call.get("mode") == "send"]
    if scenario.expect_explicit_send:
        if not send_calls:
            raise AssertionError("expected explicit project-bound send_communication send")
        modes = [call_mode(call) for call in direct_calls]
        for required in ("send_communication.precheck", "send_communication.history"):
            if required not in modes:
                raise AssertionError(f"explicit send should still run {required} first")
        if (
            modes.index("send_communication.send") < modes.index("send_communication.precheck")
            or modes.index("send_communication.send") < modes.index("send_communication.history")
        ):
            raise AssertionError("send_communication send must happen after precheck and history")
        for call in send_calls:
            if call.get("user_confirmed") is not True:
                raise AssertionError("send_communication send must pass user_confirmed=true")
            if not call.get("project_id") and not call.get("project_target_id"):
                raise AssertionError("send_communication send should be associated with a project or project target")
            if not call.get("message") or not call.get("channel"):
                raise AssertionError("send_communication send must include exact channel and message")
    elif send_calls:
        raise AssertionError("direct skills must not send unless the scenario has explicit user approval")

    for tool in scenario.expect_with_people_tools:
        matching = [call for call in direct_calls if call.get("tool") == tool]
        if not matching or not any(call.get("with_people") is True for call in matching):
            raise AssertionError(f"{tool} must be called with with_people=true")


def assert_scenario(scenario: Scenario, runtime: str, calls: list[dict[str, Any]]) -> None:
    del runtime
    assert_watch_contract(scenario, calls)
    assert_direct_contract(scenario, calls)


def run_scenario(scenario: Scenario, runtime: str) -> dict[str, Any]:
    skill_names = load_skill_names()
    if scenario.skill not in skill_names:
        raise AssertionError(f"missing skill folder for {scenario.skill}")

    mock = MockSuperCarlMCP(scenario.name, runtime)
    outputs: list[dict[str, Any]] = []
    for call in scenario.calls:
        tool = call.get("tool", "watch_signals")
        args = {key: value for key, value in call.items() if key != "tool"}
        outputs.append(mock.call(tool, resolve_placeholders(args, mock)))

    assert_scenario(scenario, runtime, mock.calls)
    return {
        "scenario": scenario.name,
        "runtime": runtime,
        "skill": scenario.skill,
        "user_prompt": scenario.user_prompt,
        "call_count": len(mock.calls),
        "calls": mock.calls,
        "modes": [call_mode(call) for call in mock.calls],
        "project_id": mock.project_id,
        "watch_config_id": mock.watch_config_id,
        "outputs": outputs,
        "status": "passed",
    }


DIRECT_SCENARIOS: list[Scenario] = [
    Scenario(
        name="direct_icp_people_search_to_project_messages",
        skill="super-carl-people-search-to-shortlist",
        user_prompt=(
            "Find ICP buyers for Super Carl among VP Sales and RevOps leaders at AI SaaS "
            "companies, add the best three to a project, and generate personalized quick-text drafts."
        ),
        calls=[
            {"tool": "agent_session", "mode": "start", "agent_name": "OpenClaw ICP search"},
            {
                "tool": "people_search",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "query": "VP Sales and RevOps leaders at AI SaaS companies",
                "role_intent": "sales",
                "include_social_proximity": True,
                "evidence_required": True,
                "limit": 10,
            },
            {
                "tool": "project_action",
                "mode": "add_targets",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "target_user_ids": ["SCENARIO_PERSON_1", "SCENARIO_PERSON_2", "SCENARIO_PERSON_3"],
                "engagement_mode": "quick_text",
                "outreach_intent_type": "finding_customers",
                "outreach_intent_description": "Offer useful GTM monitoring context to likely ICP buyers.",
                "user_confirmed": True,
            },
            {"tool": "agent_session", "mode": "status", "agent_session_id": "SCENARIO_AGENT_SESSION"},
            {
                "tool": "project_action",
                "mode": "generate_messages",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "outreach_intent_type": "finding_customers",
                "outreach_intent_description": "Offer useful GTM monitoring context to likely ICP buyers.",
                "user_confirmed": True,
            },
            {"tool": "project_action", "mode": "send_readiness", "agent_session_id": "SCENARIO_AGENT_SESSION"},
        ],
        expected_tools=("agent_session", "people_search", "project_action"),
        expect_agent_session=True,
        expect_project_binding=True,
        expect_project_grouping=True,
        expect_project_message_generation=True,
    ),
    Scenario(
        name="direct_job_search_warm_path_messages",
        skill="super-carl-job-search-warm-path",
        user_prompt=(
            "Find VP Engineering or Director Engineering jobs that fit my profile, identify "
            "hiring managers or warm paths, and draft intro requests."
        ),
        calls=[
            {"tool": "agent_session", "mode": "start", "agent_name": "Hermes job search warm paths"},
            {
                "tool": "jobs_search",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "query": "VP Engineering or Director Engineering roles in AI infrastructure",
                "with_people": True,
                "fit_profile": "Use my Super Carl profile and engineering leadership background",
                "exclude_functions": ["human resources", "finance", "legal"],
                "evidence_required": True,
                "limit": 10,
            },
            {
                "tool": "people_search",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "query": "hiring managers, engineering leaders, recruiters, and warm paths for SCENARIO_JOB_1",
                "role_intent": "job_seeker",
                "company_ids": ["SCENARIO_COMPANY_1"],
                "include_social_proximity": True,
                "evidence_required": True,
                "limit": 6,
            },
            {
                "tool": "social_proximity_research",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "target_user_id": "SCENARIO_PERSON_1",
                "status_only": False,
            },
            {
                "tool": "project_action",
                "mode": "add_targets",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "target_user_ids": ["SCENARIO_PERSON_1", "SCENARIO_PERSON_2"],
                "engagement_mode": "quick_text",
                "outreach_intent_type": "reaching_hiring_manager",
                "outreach_intent_description": "Ask for advice or a warm intro about a role that matches my engineering leadership background.",
                "user_confirmed": True,
            },
            {
                "tool": "project_action",
                "mode": "generate_messages",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "outreach_intent_type": "reaching_hiring_manager",
                "outreach_intent_description": "Ask for advice or a warm intro about a role that matches my engineering leadership background.",
                "user_confirmed": True,
            },
        ],
        expected_tools=("agent_session", "jobs_search", "project_action"),
        expect_agent_session=True,
        expect_project_binding=True,
        expect_project_grouping=True,
        expect_project_message_generation=True,
        expect_with_people_tools=("jobs_search",),
    ),
    Scenario(
        name="direct_post_activity_to_grouped_prospecting",
        skill="super-carl-post-activity-to-prospects",
        user_prompt=(
            "Search recent people who engaged with competitor posts about GTM monitoring, "
            "find ICP-fit prospects, group them in a project, and generate value-led messages."
        ),
        calls=[
            {"tool": "agent_session", "mode": "start", "agent_name": "OpenClaw post activity prospecting"},
            {
                "tool": "posts_search",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "query": "people who engaged with competitor posts about GTM monitoring in the last 14 days",
                "with_people": True,
                "role_intent": "sales",
                "evidence_required": True,
                "limit": 10,
            },
            {
                "tool": "people_search",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "query": "ICP-fit people from recent competitor post engagement",
                "source_tool": "posts_search",
                "post_ids": ["SCENARIO_POST_1"],
                "role_intent": "sales",
                "include_social_proximity": True,
                "evidence_required": True,
                "limit": 6,
            },
            {
                "tool": "project_action",
                "mode": "add_targets",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "target_user_ids": ["SCENARIO_PERSON_1", "SCENARIO_PERSON_2"],
                "outreach_intent_type": "finding_customers",
                "outreach_intent_description": "Share a useful GTM monitoring resource tied to the cited topic.",
                "user_confirmed": True,
            },
            {
                "tool": "project_action",
                "mode": "generate_messages",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "outreach_intent_type": "finding_customers",
                "outreach_intent_description": "Share a useful GTM monitoring resource tied to the cited topic.",
                "user_confirmed": True,
            },
        ],
        expected_tools=("agent_session", "posts_search", "people_search", "project_action"),
        expect_agent_session=True,
        expect_project_binding=True,
        expect_project_grouping=True,
        expect_project_message_generation=True,
        expect_with_people_tools=("posts_search",),
    ),
    Scenario(
        name="direct_project_outreach_review_single_target",
        skill="super-carl-project-outreach-review",
        user_prompt=(
            "Review the top target in this project, inspect evidence and prior context, draft a "
            "personal quick text, and save it for review without sending."
        ),
        calls=[
            {"tool": "agent_session", "mode": "start", "agent_name": "Hermes outreach review"},
            {
                "tool": "agent_session",
                "mode": "switch_project",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
            },
            {"tool": "project_action", "mode": "targets", "agent_session_id": "SCENARIO_AGENT_SESSION", "project_id": "SCENARIO_PROJECT", "include_evidence": True},
            {
                "tool": "people_lookup_batch",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "profiles": [{"target_user_id": "SCENARIO_PERSON_1"}],
                "relationship_detail": "intro_paths",
            },
            {
                "tool": "send_communication",
                "mode": "precheck",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "channels": ["gmail_send", "linkedin_send_message", "supercarl_referral_request"],
            },
            {
                "tool": "send_communication",
                "mode": "history",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "history_fresh": True,
            },
            {
                "tool": "send_communication",
                "mode": "draft",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "channel": "linkedin_send_message",
                "message": "Personalized draft using cited evidence and warm-path context.",
                "approval_required": True,
            },
            {
                "tool": "project_action",
                "mode": "update_message",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "message": "Personalized draft using cited evidence and warm-path context.",
                "review_action": "save",
                "user_confirmed": True,
            },
        ],
        expected_tools=("agent_session", "project_action", "people_lookup_batch", "send_communication"),
        expect_agent_session=True,
        expect_project_binding=True,
        expect_send_draft=True,
    ),
    Scenario(
        name="direct_project_outreach_explicit_single_send",
        skill="super-carl-project-outreach-review",
        user_prompt=(
            "Send the reviewed LinkedIn message to the selected project target now. "
            "Use the current Super Carl session project and selected target. "
            "Use this exact draft I approved: The exact reviewed message the user approved."
        ),
        calls=[
            {"tool": "agent_session", "mode": "start", "agent_name": "OpenClaw approved project send"},
            {
                "tool": "agent_session",
                "mode": "switch_project",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
            },
            {"tool": "project_action", "mode": "targets", "agent_session_id": "SCENARIO_AGENT_SESSION", "project_id": "SCENARIO_PROJECT", "include_evidence": True},
            {
                "tool": "send_communication",
                "mode": "precheck",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "channels": ["linkedin_send_message"],
            },
            {
                "tool": "send_communication",
                "mode": "history",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "history_fresh": True,
            },
            {
                "tool": "send_communication",
                "mode": "send",
                "agent_session_id": "SCENARIO_AGENT_SESSION",
                "project_id": "SCENARIO_PROJECT",
                "project_target_id": "SCENARIO_PROJECT_TARGET_1",
                "channel": "linkedin_send_message",
                "message": "The exact reviewed message the user approved.",
                "user_confirmed": True,
            },
        ],
        expected_tools=("agent_session", "project_action", "send_communication"),
        expect_agent_session=True,
        expect_project_binding=True,
        expect_explicit_send=True,
    ),
]


WATCH_SCENARIOS: list[Scenario] = [
    Scenario(
        name="account_intent_daily_digest",
        skill="super-carl-account-intent-watch",
        user_prompt="Watch my spreadsheet of target accounts for GTM hiring, leadership moves, category posts, and warm paths.",
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Target account intent watch",
                "role_intent": "gtm",
                "source_kind": "spreadsheet",
                "sources": [{"source_kind": "spreadsheet", "url": "https://docs.google.com/spreadsheets/d/example", "label": "Target accounts"}],
                "watch_prompt": "Watch target accounts for timing signals and warm paths.",
                "signal_types": ["hiring_spike", "company_growth", "posts", "role_change", "warm_intro"],
                "delivery_channels": ["project_feed", "app_push", "email_digest"],
                "action_policy": {"default_action": "add_to_review_queue", "never_send_without_approval": True},
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_message"]},
        ],
        expected_source_kinds=("spreadsheet",),
        expected_signal_types=("hiring_spike", "company_growth", "posts", "role_change", "warm_intro"),
        expected_role_intent="gtm",
        expect_create_or_update=True,
        expect_promote=True,
    ),
    Scenario(
        name="competitor_engagement_icp_followup",
        skill="super-carl-competitor-engagement-watch",
        user_prompt="Look over my market for people liking or commenting on competitor posts and prepare value-led follow-up.",
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Competitor engagement radar",
                "role_intent": "sales",
                "source_kind": "competitor_set",
                "sources": [{"source_kind": "competitor_set", "value": "Competitor A; Competitor B"}],
                "watch_prompt": "Find people engaging with competitor posts, rank top ICP-fit people, and include warm intro paths.",
                "signal_types": ["competitor_engagement", "posts", "warm_intro"],
                "delivery_channels": ["project_feed", "email_digest"],
                "action_policy": {"default_action": "draft_message", "never_send_without_approval": True},
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_message"]},
        ],
        expected_source_kinds=("competitor_set",),
        expected_signal_types=("competitor_engagement", "posts", "warm_intro"),
        expected_role_intent="sales",
        expect_create_or_update=True,
        expect_promote=True,
    ),
    Scenario(
        name="owned_audience_post_engagement",
        skill="super-carl-owned-audience-follow-up",
        user_prompt="Watch people who like my posts about GTM monitoring and tell me who is worth following up with.",
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Owned audience follow-up",
                "role_intent": "founder",
                "source_kind": "owner_posts",
                "sources": [{"source_kind": "owner_posts", "value": "Posts about GTM monitoring"}, {"source_kind": "network_scope", "value": "1st and 2nd degree paths"}],
                "watch_prompt": "Watch engagement on my posts and find useful follow-ups.",
                "signal_types": ["liked_my_post", "follow_up", "warm_intro"],
                "delivery_channels": ["project_feed", "app_push", "email_digest"],
                "action_policy": {"default_action": "add_to_review_queue", "never_send_without_approval": True},
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_message"]},
        ],
        expected_source_kinds=("owner_posts", "network_scope"),
        expected_signal_types=("liked_my_post", "follow_up", "warm_intro"),
        expected_role_intent="founder",
        expect_create_or_update=True,
        expect_promote=True,
    ),
    Scenario(
        name="job_seeker_profile_matched_roles",
        skill="super-carl-job-seeker-opportunity-watch",
        user_prompt="Use my profile to monitor senior product roles, recruiter posts, hiring managers, and warm intro paths.",
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Senior product roles worth applying to",
                "role_intent": "job_seeker",
                "source_kind": "owner_profile",
                "sources": [
                    {"source_kind": "owner_profile", "value": "Use my Super Carl profile and work history"},
                    {"source_kind": "account_list", "value": "AI infrastructure and developer tools"},
                    {"source_kind": "job_search", "value": "Senior product roles, remote or Bay Area"},
                    {"source_kind": "network_scope", "value": "Hiring managers, recruiters, alumni, and coworkers"},
                ],
                "watch_prompt": "Find new senior product roles that fit my profile.",
                "signal_types": ["jobs", "employee_post", "company_growth", "warm_intro"],
                "delivery_channels": ["project_feed", "email_digest"],
                "action_policy": {"default_action": "draft_intro_request", "never_send_without_approval": True},
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_intro_request"]},
        ],
        expected_source_kinds=("owner_profile", "job_search", "network_scope"),
        expected_signal_types=("jobs", "employee_post", "company_growth", "warm_intro"),
        expected_role_intent="job_seeker",
        expect_create_or_update=True,
        expect_promote=True,
    ),
    Scenario(
        name="recruiter_candidate_radar",
        skill="super-carl-recruiter-candidate-radar",
        user_prompt="Watch this candidate spreadsheet and competitor alumni list for role changes, technical posts, and team warm paths.",
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Founding AI engineer candidate radar",
                "role_intent": "recruiter",
                "source_kind": "spreadsheet",
                "sources": [{"source_kind": "spreadsheet", "url": "https://docs.google.com/spreadsheets/d/example", "label": "Candidate source"}, {"source_kind": "people_list", "value": "Known AI infra candidates"}, {"source_kind": "network_scope", "value": "Team warm paths"}],
                "watch_prompt": "Rank high-fit candidates and cite source row and warm path.",
                "signal_types": ["role_change", "employee_post", "posts", "warm_intro"],
                "delivery_channels": ["project_feed", "email_digest"],
                "action_policy": {"default_action": "draft_message", "never_send_without_approval": True},
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_message"]},
        ],
        expected_source_kinds=("spreadsheet", "people_list", "network_scope"),
        expected_signal_types=("role_change", "employee_post", "posts", "warm_intro"),
        expected_role_intent="recruiter",
        expect_create_or_update=True,
        expect_promote=True,
    ),
    Scenario(
        name="champion_mover_weekly_profile_updates",
        skill="super-carl-champion-mover",
        user_prompt="Watch former customers, advisors, and coworkers for role changes with weekly profile update cadence.",
        calls=[
            {"mode": "role_packs"},
            {
                "mode": "create",
                "title": "Champion mover watch",
                "role_intent": "networking",
                "source_kind": "people_list",
                "sources": [{"source_kind": "people_list", "value": "Former customers, advisors, and coworkers"}, {"source_kind": "network_scope", "value": "Use social proximity"}],
                "watch_prompt": "Surface relationship-aware role-change follow-ups.",
                "signal_types": ["role_change", "follow_up", "warm_intro"],
                "delivery_channels": ["project_feed", "app_push", "email_digest"],
                "freshness_policy": {"profile_updates": "weekly_or_when_new_bulk_ingest_arrives"},
                "action_policy": {"default_action": "draft_message", "never_send_without_approval": True},
            },
            {"mode": "run_now"},
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_message"]},
        ],
        expected_source_kinds=("people_list", "network_scope"),
        expected_signal_types=("role_change", "follow_up", "warm_intro"),
        expected_role_intent="networking",
        expect_create_or_update=True,
        expect_promote=True,
        expect_freshness_policy=True,
    ),
    Scenario(
        name="warm_intro_review_existing_hits",
        skill="super-carl-warm-intro-outreach",
        user_prompt="Look at this project's current hits, tell me who has the best warm path, and prepare a reviewed draft for the top one.",
        calls=[
            {"mode": "hits"},
            {"mode": "evidence", "signal_hit_id": "SCENARIO_HIT"},
            {"mode": "promote_hit", "signal_hit_id": "SCENARIO_HIT", "draft_message": True, "actions": ["draft_message"]},
        ],
        expect_promote=True,
    ),
    Scenario(
        name="agent_webhook_digest_delivery",
        skill="super-carl-agent-webhook-digests",
        user_prompt="Configure my OpenClaw callback for this Super Carl project and verify callback delivery.",
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
        expect_create_or_update=True,
        expect_promote=False,
        expect_webhook=True,
    ),
]

SCENARIOS: list[Scenario] = DIRECT_SCENARIOS + WATCH_SCENARIOS


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
    widths = [max(len(headers[index]), *(len(row[index]) for row in rows)) for index in range(len(headers))]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    print(f"\nPassed {len(results)} simulated agent flows")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Super Carl agent skill user-flow simulations.")
    parser.add_argument("--runtime", choices=AGENT_RUNTIMES, action="append", help="Runtime to simulate. May be passed more than once. Defaults to both.")
    parser.add_argument("--scenario", action="append", help="Scenario name to run. May be passed more than once. Defaults to all.")
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
