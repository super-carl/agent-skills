---
name: super-carl-warm-intro-outreach
description: Turn Super Carl watch hits into warm-intro review flows by inspecting evidence, social proximity, and message context before adding targets or drafting outreach.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, job_seeker, recruiter, investor, bd, networking]
    primary_tool: watch_signals
---

# Super Carl Warm Intro Outreach

Use this after `watch_signals` has produced hits and the user asks which ones are worth acting on, who has a warm path, or how to draft reviewed outreach.

## Flow

1. Call `watch_signals` with `mode: "hits"` for the project.
2. For each promising hit, call `mode: "evidence"`.
3. Compare match reasons, evidence citations, social proximity, receptivity, and the user's role intent.
4. Recommend a small set of reviewable actions.
5. Use `mode: "promote_hit"` with `draft_message: true` when the user approves adding a hit to project review.
6. Tell the user that sending remains approval-gated in Super Carl.

## Example Promote

```json
{
  "mode": "promote_hit",
  "project_id": "PROJECT_ID",
  "signal_hit_id": "SIGNAL_HIT_ID",
  "draft_message": true,
  "actions": ["draft_message"]
}
```

## Draft Evaluation

Before promoting, check:

- Does the opener cite a real evidence item?
- Is the value angle useful for the recipient?
- Is social proximity strong enough to suggest a warm intro?
- Does the role intent change the tone, for example job seeker versus recruiter versus founder?
- Would this message feel natural if the recipient inspected why they were contacted?

## Guardrails

- Never send from this skill.
- Never invent a warm path. Use the social proximity evidence returned by Super Carl.
- If evidence is insufficient, recommend dismissing, snoozing, or watching longer instead of drafting.
