---
name: Pylint 10.00/10 standard
description: Project maintains strict pylint 10.00/10 — how violations are handled
type: project
originSessionId: 6212b077-103f-442a-86d1-e3929dce3ad5
---
All Python files (`function_app.py`, `traveller_map_fetch.py`, `shared/helpers.py`, world generation modules) must score 10.00/10 under `.venv/bin/pylint`.

**Why:** Enforced throughout the project's history; each session ends with a pylint check.

**How to apply:** After any code change, run `.venv/bin/pylint function_app.py traveller_map_fetch.py shared/helpers.py` before reporting the task done. Common suppressions used in this codebase:
- `# pylint: disable=too-many-arguments,too-many-positional-arguments` — on helpers with 5+ params
- `# pylint: disable=too-many-locals` — on complex generation functions
- `# pylint: disable=too-many-instance-attributes` — on dataclasses (put on class line, not decorator)
- `# pylint: disable=import-outside-toplevel` — around CLI `import argparse` / `import sys` inside `main()`
- `# pylint: disable=missing-function-docstring` — on `main()` alongside `too-many-return-statements`
