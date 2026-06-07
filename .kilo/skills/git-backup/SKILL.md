---
name: git-backup
description: Stages all changes, auto-generates a categorised multi-line commit message, commits, and pushes to origin.
---

# Skill: Git Backup

## Purpose
Stage all working-tree changes, generate a structured commit message categorised by file type (scripts/slides/answer_keys/templates/skills-commands), confirm with the user, commit, and push to origin.

## Prerequisites
- Git remote `origin` configured

## Workflow

### Step 1: Check working tree
```powershell
git status
```
If "nothing to commit, working tree clean" — stop here.

### Step 2: Stage everything
```powershell
git add -A
```

### Step 3: Show staged diff summary
```powershell
git diff --cached --stat
```

### Step 4: Build categorised commit message

**Subject line format:** `Entry Ticket N — {brief description}` (e.g., `Entry Ticket 1 — Compound sentences grammar focus`)

**Body categories:** Parse `git diff --cached --name-status` into:
- Skills / Commands (`.kilo/`)
- Scripts (`scripts/`)
- Slides (`slides/`)
- Answer keys (`ANSWER_KEYS/`)
- Templates (`templates/`)
- Config (`config/`)

**Full message structure:**
```
Entry Ticket N — {description}

Skills/commands:
- ...

Scripts:
- ...

Slides:
- ...

Answer keys:
- ...

Templates:
- ...

Config:
- ...
```

### Step 5: Confirm with user
Display the generated message. Ask `Commit with this message? (Y/n)`:
- **Y** or empty — commit with the generated message (via `-F` temp file)
- **N** — prompt for custom message; empty = abort

### Step 6: Push
```powershell
git push origin main
```

### Step 7: Report
```powershell
$ahead = [int](git rev-list --count origin/main..HEAD)
Write-Host "Committed (${ahead} ahead of origin)"
```

## Edge cases
- **Nothing to commit**: stop before staging
- **Push fails**: error is printed; local commit is preserved
- **Custom message rejected**: empty message aborts the operation
