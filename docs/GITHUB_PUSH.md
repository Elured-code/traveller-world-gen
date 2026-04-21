# Pushing to GitHub

The local repository has already been initialised with an initial commit.
These instructions cover creating the GitHub repository and pushing to it.

---

## Prerequisites

- A [GitHub account](https://github.com)
- Git installed locally
- The project cloned or copied to your machine with the `.git/` directory intact

---

## Option A — GitHub CLI (recommended)

The `gh` CLI creates the repository and pushes in one step.

### Install gh

```bash
# macOS
brew install gh

# Windows (winget)
winget install GitHub.cli

# Linux (apt)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh
```

```powershell
# Windows (winget)
winget install GitHub.cli

# Windows (Scoop)
scoop install gh
```

### Authenticate and push

```bash
gh auth login
gh repo create traveller-world-gen \
    --public \
    --description "Traveller RPG world and star system generator (CRB + WBH rules) with Azure Functions REST API" \
    --push \
    --source .
```

```powershell
gh auth login
gh repo create traveller-world-gen `
    --public `
    --description "Traveller RPG world and star system generator (CRB + WBH rules) with Azure Functions REST API" `
    --push `
    --source .
```

Replace `--public` with `--private` if you prefer a private repository.

---

## Option B — GitHub web UI + git push

### 1. Create the repository on GitHub

1. Go to [github.com/new](https://github.com/new)
2. Set **Repository name** to `traveller-world-gen`
3. Add a description (optional):
   > Traveller RPG world and star system generator (CRB + WBH rules) with Azure Functions REST API
4. Choose **Public** or **Private**
5. **Do not** initialise with a README, .gitignore, or licence — the local repo already has all of these
6. Click **Create repository**

### 2. Add the remote and push

Copy the HTTPS or SSH URL from the repository page, then run:

```bash
# HTTPS
git remote add origin https://github.com/<your-username>/traveller-world-gen.git
git push -u origin main

# SSH (if you have an SSH key configured)
git remote add origin git@github.com:<your-username>/traveller-world-gen.git
git push -u origin main
```

```powershell
# HTTPS
git remote add origin https://github.com/<your-username>/traveller-world-gen.git
git push -u origin main

# SSH (if you have an SSH key configured)
git remote add origin git@github.com:<your-username>/traveller-world-gen.git
git push -u origin main
```

---

## Verifying the push

```bash
git remote -v
git log --oneline
```

```powershell
git remote -v
git log --oneline
```

Both should show `origin` pointing to your GitHub repository and the initial
commit hash. Open `https://github.com/<your-username>/traveller-world-gen` in
a browser to confirm the files are visible.

---

## After pushing

### Set up local.settings.json

The file `local.settings.json` is intentionally excluded from the repository
(it can contain Azure storage connection strings). Copy the committed template
and fill in your values before running the Azure Functions host locally:

```bash
cp local.settings.json.example local.settings.json
```

```powershell
Copy-Item local.settings.json.example local.settings.json
```

### Add a GitHub Actions workflow (optional)

To run the test suite automatically on every push, create
`.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pytest jsonschema
      - run: pytest tests/ -v
```

### Protect the main branch (optional)

In **Settings → Branches → Branch protection rules**, add a rule for `main`
and enable **Require a pull request before merging** to prevent direct pushes.
