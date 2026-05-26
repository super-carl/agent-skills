# Validation

Local validation:

```bash
python3 scripts/validate_skills.py
```

Deterministic user-flow simulations for OpenClaw and Hermes Agent:

```bash
python3 scripts/simulate_user_flows.py
```

The simulation harness covers account intent, competitor engagement, owned audience follow-up, job seeker watches, recruiter candidate radar, champion mover watches, warm intro review, and `agent_webhook` delivery. It asserts that flows use inspectable evidence before promotion, preserve approval-gated outreach, include expected source/signal contracts, and keep `project_feed` enabled when `agent_webhook` is configured.

OpenClaw validation from a sibling checkout:

```bash
python3 ../openclaw-fresh/skills/skill-creator/scripts/quick_validate.py skills/super-carl-account-intent-watch
```

Hermes Agent validation from a sibling checkout:

```bash
python3 - <<'PY'
from pathlib import Path
import importlib.util

tool_path = Path("../hermes-agent-fresh/tools/skill_manager_tool.py").resolve()
spec = importlib.util.spec_from_file_location("skill_manager_tool", tool_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

for skill in sorted(Path("skills").glob("*/SKILL.md")):
    err = mod._validate_frontmatter(skill.read_text())
    if err:
        raise SystemExit(f"{skill}: {err}")
print("Hermes frontmatter validation passed")
PY
```
