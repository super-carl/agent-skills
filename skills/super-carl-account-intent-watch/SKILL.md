---
name: super-carl-account-intent-watch
description: Configure a hosted Super Carl watch for account-list timing signals, hiring spikes, leadership changes, topic posts, warm paths, and daily/weekly review digests.
license: MIT
metadata:
  super_carl:
    role_intents: [gtm, founder, sales, bd, investor]
    primary_tool: watch_signals
---

# Super Carl Account Intent Watch

Use this when the user wants Carl to monitor a company/account list over time and surface timing signals that justify a reviewable next action.

## Flow

1. Ask for the outcome, role intent, account source, and preferred cadence if missing.
2. Call `watch_signals` with `mode: "role_packs"` when you need pack defaults.
3. Create or update a hosted watch with `mode: "create"` or `mode: "update"`.
4. Use `source_kind: "account_list"` or `source_kind: "spreadsheet"` for durable lists.
5. Include signal lanes such as `hiring_spike`, `company_growth`, `posts`, `role_change`, and `warm_intro`.
6. Include `delivery_channels: ["project_feed", "app_push", "email_digest"]`; add `agent_webhook` only if the user configured a callback.
7. Inspect `hits`, then fetch `evidence` for promising hits before drafting.
8. Use `promote_hit` with `draft_message: true` only when the hit has inspectable evidence and the user wants it in review.

## Example Create

```json
{
  "mode": "create",
  "title": "Mid-market RevOps account intent",
  "role_intent": "gtm",
  "source_kind": "spreadsheet",
  "sources": [
    {
      "source_kind": "spreadsheet",
      "url": "https://docs.google.com/spreadsheets/d/example",
      "label": "Target accounts"
    }
  ],
  "watch_prompt": "Watch these accounts for GTM hiring, leadership changes, posts about pipeline quality, and warm intro paths. Send a daily digest only when new evidence appears.",
  "signal_types": ["hiring_spike", "company_growth", "posts", "role_change", "warm_intro"],
  "delivery_channels": ["project_feed", "app_push", "email_digest"],
  "action_policy": {
    "default_action": "add_to_review_queue",
    "never_send_without_approval": true
  }
}
```

## Message Guidance

Drafts should explain why now with account evidence first. Good openers cite the concrete trigger: a job post, hiring spike, leadership move, company post, or warm path. Do not imply intent from weak signals.

## Guardrails

- Super Carl owns scheduling; do not run an agent-side polling loop.
- Do not send outreach from this skill. Keep all messages approval-gated.
- If `evidence` is thin, suggest watching longer or narrowing the account source.
