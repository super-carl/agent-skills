---
name: super-carl-owned-audience-follow-up
description: Configure a hosted Super Carl watch for people engaging with the user's own posts, profile, or audience signals, then create respectful evidence-backed follow-up drafts.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, networking]
    primary_tool: watch_signals
---

# Super Carl Owned Audience Follow-Up

Use this when the user wants Carl to watch who likes, comments on, reposts, or otherwise engages with their own posts and then surface the best people for value-led follow-up.

## Flow

1. Use the Super Carl MCP tool `watch_signals`; identify the user's topic, product context, and desired audience.
2. Create a hosted watch with sources `owner_posts`, `owned_audience`, and optionally `network_scope`.
3. Use signals `liked_my_post`, `follow_up`, `posts`, and `warm_intro`.
4. Ask for evidence that includes post snippet, engagement actor, engagement type, and timestamp.
5. Inspect `hits` and fetch `evidence` before drafting.
6. Use `promote_hit` with `draft_message: true` only for hits the user wants to review.

## Example Create

```json
{
  "mode": "create",
  "title": "Owned audience follow-up",
  "role_intent": "founder",
  "source_kind": "owner_posts",
  "sources": [
    { "source_kind": "owner_posts", "value": "Posts about GTM monitoring and social proximity" },
    { "source_kind": "network_scope", "value": "1st and 2nd degree reachable paths" }
  ],
  "watch_prompt": "Watch people who engage with my posts about GTM monitoring. Pick top ICP-fit people, show warm paths, and draft helpful follow-ups that mention the specific post only when evidence is available.",
  "signal_types": ["liked_my_post", "follow_up", "warm_intro"],
  "delivery_channels": ["project_feed", "app_push", "email_digest"],
  "action_policy": {
    "default_action": "add_to_review_queue",
    "never_send_without_approval": true
  }
}
```

## Message Guidance

Good drafts use a concrete, respectful opener: "Thanks for engaging with my post about X. I thought you might find Y useful." The rest should offer value, not a hard pitch.

## Guardrails

- Do not fabricate post topics or engagement details.
- Use `evidence` before writing a specific opener.
- Never send without approval.
