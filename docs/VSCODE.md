# VS Code Configuration Guide

This guide explains how to configure Visual Studio Code so that it uses the
same Python environment as Claude Code. When both share the same `.venv-1`,
import resolution, linting, and type checking produce consistent results.

---

## Why this matters

VS Code runs several independent tools — Pylance (IntelliSense), the Pylint
extension, and the Python test runner — each with its own path configuration.
If any of these resolves to a different Python than the project `.venv-1`, you
will see errors in the Problems panel that Claude does not see (or vice versa),
because they are literally running against different package sets.

Claude Code invokes Python tools explicitly via `.venv-1/bin/python` and
`.venv-1/bin/pylint` in the terminal. The settings below make VS Code do the
same.

---

## Prerequisites

The project virtual environment must be created and all dependencies installed
before configuring VS Code. The project venv is named `.venv-1` (not `.venv`).

```bash
python3.11 -m venv .venv-1
source .venv-1/bin/activate          # macOS / Linux
# .venv-1\Scripts\Activate.ps1       # Windows PowerShell
pip install -r requirements.txt
pip install pylint
```

The gen-ui desktop app has its own dependency (PySide6). Install it into the
same venv:

```bash
pip install -r gen-ui/requirements.txt
```

Verify:

```bash
.venv-1/bin/python -c "import azure.functions; print('OK')"
.venv-1/bin/python -c "import PySide6; print('OK')"
.venv-1/bin/pylint --version
```

---

## Required extensions

Install from the Extensions panel or accept the workspace prompt when you open
the project (`.vscode/extensions.json` lists them as recommendations).

| Extension | ID | Purpose |
|-----------|----|---------|
| Python | `ms-python.python` | Interpreter selection, test runner, debugger |
| Pylance | `ms-python.vscode-pylance` | IntelliSense, import resolution, type checking |
| Pylint | `ms-python.pylint` | Lint errors and warnings in the Problems panel |
| Azure Functions | `ms-azuretools.vscode-azurefunctions` | Local function host, deploy commands |

---

## Workspace settings explained

All settings below are already present in `.vscode/settings.json`. This section
explains what each one does and why it is needed.

### Python interpreter

```json
"python.defaultInterpreterPath": "${workspaceFolder}/.venv-1/bin/python"
```

Sets `.venv-1` as the fallback interpreter for the test runner and debugger.
This is **not** sufficient on its own — Pylance and Pylint each need additional
settings, and the interpreter must also be actively selected (see below).

---

### Pylance — IntelliSense and import resolution

```json
"python.analysis.venvPath": "${workspaceFolder}",
"python.analysis.venv": ".venv-1",
"python.analysis.extraPaths": ["${workspaceFolder}"],
"python.analysis.typeCheckingMode": "basic"
```

| Setting | Purpose |
|---------|---------|
| `python.analysis.venvPath` | Tells Pylance where to look for virtual environments |
| `python.analysis.venv` | Names the specific venv to use (`.venv-1`) |
| `python.analysis.extraPaths` | Adds the project root so local modules resolve |
| `python.analysis.typeCheckingMode` | `"basic"` matches the level used in development |

Without `venvPath` + `venv`, Pylance cannot find third-party packages such as
`azure.functions` or `PySide6` and shows false "import could not be resolved"
errors even when the package is correctly installed in `.venv-1`.

---

### Pylint extension — Problems panel linting

```json
"pylint.path": ["${workspaceFolder}/.venv-1/bin/pylint"],
"pylint.interpreter": ["${workspaceFolder}/.venv-1/bin/python"]
```

The Pylint extension runs as a separate process with its own path resolution.
Without these settings it falls back to whatever `pylint` is on your system
`$PATH` — typically a global install that lacks the project packages and
produces different results from Claude's terminal runs.

---

## Selecting the interpreter

`defaultInterpreterPath` is only a fallback; it is overridden by any previously
stored selection. To ensure the active interpreter is `.venv-1`:

1. `Cmd+Shift+P` → **Python: Select Interpreter**
2. Choose the entry showing `.venv-1` — e.g. `Python 3.11.x ('.venv-1': venv)`

The selected interpreter appears in the status bar at the bottom of the window.
Pylance picks it up immediately.

---

## Verifying the setup

**Pylance** — open any `.py` file importing `azure.functions`. The import
should resolve without a squiggle. If it does not, run
**Pylance: Restart Language Server** from the Command Palette.

**Pylint** — open `function_app.py`. The Problems panel should be clear.
If stale warnings remain, run **Pylint: Restart Server**.

**Terminal** — confirm the environment matches:

```bash
.venv-1/bin/python -m pylint function_app.py
# Expected: Your code has been rated at 10.00/10
```

---

## How Claude Code uses the environment

Claude Code does not auto-activate the `.venv-1` — its Bash tool inherits the
system shell environment. Every Python invocation in this project therefore
uses the explicit venv path:

```bash
.venv-1/bin/python          # not: python
.venv-1/bin/pip             # not: pip
.venv-1/bin/python -m pylint  # not: pylint
.venv-1/bin/pytest          # not: pytest
```

This is equivalent to what VS Code does when the settings above are applied,
so both environments resolve the same packages, the same pylint configuration,
and the same type stubs.

---

## Troubleshooting

**Import errors persist after setting up the venv**

Run **Developer: Reload Window**. Pylance caches import data and sometimes
needs a full restart to pick up a newly selected interpreter.

**Pylint shows different warnings from the terminal**

Open the Output panel, select **Pylint** from the dropdown, and check the path
in the startup log. If it does not show `.venv-1/bin/pylint`, confirm
`pylint.path` is saved in `.vscode/settings.json` and run
**Pylint: Restart Server**.

**`azure.functions` still unresolved after selecting `.venv-1`**

The package may not be installed. Verify with:

```bash
.venv-1/bin/python -c "import azure.functions; print(azure.functions.__version__)"
```

If this fails, run `.venv-1/bin/pip install -r requirements.txt` and reload the
window.

**Wrong interpreter shown in the status bar**

The status bar interpreter overrides `defaultInterpreterPath`. Use
**Python: Select Interpreter** to correct it.

**`PySide6` unresolved in `gen-ui/app.py`**

PySide6 must be installed in `.venv-1`:

```bash
.venv-1/bin/pip install -r gen-ui/requirements.txt
```

Then run **Pylance: Restart Language Server**.
