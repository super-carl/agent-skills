#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MAX_DESCRIPTION = 1024
REQUIRED_TERMS = ("watch_signals", "evidence", "approval")


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter")
    match = re.search(r"\n---\s*\n", text[4:])
    if not match:
        raise ValueError("missing closing frontmatter")
    raw = text[4: match.start() + 4]
    body = text[match.end() + 4:]
    data = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data, body


def main():
    names = set()
    failures = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        rel = skill_md.relative_to(ROOT)
        try:
            frontmatter, body = parse_frontmatter(skill_md.read_text())
            name = frontmatter.get("name", "")
            description = frontmatter.get("description", "")
            if not name:
                raise ValueError("frontmatter must include name")
            if name in names:
                raise ValueError(f"duplicate skill name {name}")
            names.add(name)
            if not description:
                raise ValueError("frontmatter must include description")
            if len(description) > MAX_DESCRIPTION:
                raise ValueError("description exceeds 1024 characters")
            lowered = body.lower()
            for term in REQUIRED_TERMS:
                if term not in lowered:
                    raise ValueError(f"missing required term: {term}")
            if "auto-send" in lowered or "autosend" in lowered:
                raise ValueError("unsafe auto-send wording")
        except Exception as exc:
            failures.append(f"{rel}: {exc}")

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Validated {len(names)} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
