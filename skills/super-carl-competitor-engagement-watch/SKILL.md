---
name: super-carl-competitor-engagement-watch
description: Configure a hosted Super Carl watch for people engaging with competitor posts, then rank ICP-fit contacts with evidence and warm paths for reviewed outreach.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales]
    primary_tool: watch_signals
---

# Super Carl Competitor Engagement Watch

Use this when the user asks to monitor competitor posts, competitor company activity, or category conversations and identify people who are likely worth a timely follow-up.

## Flow

1. Capture the competitor set, ICP, excluded accounts, value angle, and cadence.
2. Create a `watch_signals` watch with `source_kind: "competitor_set"`.
3. Include `signal_types: ["competitor_engagement", "posts", "warm_intro"]`.
4. Ask Super Carl to preserve post URL/snippet, actor, action type, timestamp, ICP reason, and social proximity in hit evidence.
5. Use `hits` to inspect new signals and `evidence` before drafting.
6. Include `action_policy.never_send_without_approval: true` on the watch create/update. Use `promote_hit` only for strong ICP and receptivity matches; keep delivery approval-gated.

## Example Create

```json
{
  "mode": "create",
  "title": "Competitor engagement radar",
  "role_intent": "sales",
  "source_kind": "competitor_set",
  "sources": [
    { "source_kind": "competitor_set", "value": "Competitor A; Competitor B" },
    { "source_kind": "freeform_scope", "value": "VP Sales, RevOps, and GTM leaders at B2B SaaS companies with 50-1000 employees" }
  ],
  "watch_prompt": "Look for people engaging with competitor posts about pipeline inspection, outbound quality, and GTM monitoring. Rank top ICP-fit people with warm intro paths and send a daily digest when changed.",
  "signal_types": ["competitor_engagement", "posts", "warm_intro"],
  "delivery_channels": ["project_feed", "email_digest"],
  "action_policy": {
    "default_action": "draft_message",
    "never_send_without_approval": true
  }
}
```

## Message Guidance

Lead with value, not surveillance. Prefer: "I noticed your comment on the pipeline-quality thread and thought this breakdown might be useful..." Avoid wording that feels like the user was tracked.

## Guardrails

- Use `evidence` citations before any draft.
- Do not omit `action_policy`; competitor engagement follow-up must stay approval-gated at watch creation time.
- Do not claim the person has purchase intent unless the evidence supports it.
- Do not send directly; require approval inside the Super Carl project.
