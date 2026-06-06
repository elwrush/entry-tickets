---
name: git-pages
description: Deploy the entry ticket slideshow to GitHub Pages via gh-pages branch. Creates the branch on first deploy, updates on subsequent runs. Uses git worktree isolation — never switches the main working tree branch.
---

# Skill: Git Pages

## Purpose

Deploy the entry ticket slideshow (`slides/index.html` + `slides/assets/`) to GitHub Pages so the teacher can open it in a browser without a local server. The slideshow is hosted at `https://elwrush.github.io/entry-tickets/`.

## Prerequisites
- `gh` CLI authenticated (`gh auth status`)
- `slides/index.html` exists (run `scripts/build_test_slides.py` first)
- Remote `origin` is a GitHub repo (set up by `gh repo create`)

## Workflow

---

### Step 0: Check slideshow exists

```powershell
if (-not (Test-Path "slides/index.html")) {
    Write-Error "No slideshow found at slides/index.html — run scripts/build_test_slides.py first"
    exit 1
}
```

### Step 1: Check prerequisites

```powershell
if (-not (gh auth status 2>&1 | Select-String "Logged in")) {
    Write-Error "gh CLI not authenticated — run 'gh auth login' first"
    exit 1
}
```

### Step 2: Detect remote

```powershell
$remoteUrl = git remote get-url origin
if ($remoteUrl -match "github\.com[:\/](.+)/(.+)\.git") {
    $owner = $matches[1]
    $repo = $matches[2]
} else {
    Write-Error "Remote origin is not a GitHub repo"
    exit 1
}
```

### Step 3: Copy slideshow to staging

```powershell
$staging = "$env:TEMP\entry-tickets-gh-pages-staging"
if (Test-Path $staging) { Remove-Item -Recurse -Force -Path $staging }
New-Item -ItemType Directory -Force -Path $staging | Out-Null
Copy-Item -Recurse -Force "slides\*" "$staging\"
Write-Host "  Copied slideshow to staging"
```

### Step 4: Create or reuse gh-pages worktree

```powershell
$worktreeDir = "$env:TEMP\entry-tickets-gh-pages-worktree"

# Remove any leftover worktree
git worktree remove $worktreeDir 2>$null
if (Test-Path $worktreeDir) { Remove-Item -Recurse -Force -Path $worktreeDir }

# Fetch remote gh-pages branch
git fetch origin gh-pages 2>$null
$ghPagesExists = $LASTEXITCODE -eq 0

if ($ghPagesExists) {
    Write-Host "Adding worktree for existing gh-pages branch..."
    git worktree add $worktreeDir gh-pages 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create worktree"
        exit 1
    }
} else {
    # First deploy: create gh-pages branch from isolated temp repo
    Write-Host "Creating gh-pages branch for first deploy..."
    $bootstrapDir = "$env:TEMP\entry-tickets-gh-pages-bootstrap"
    if (Test-Path $bootstrapDir) { Remove-Item -Recurse -Force $bootstrapDir }
    New-Item -ItemType Directory -Force -Path $bootstrapDir | Out-Null
    Push-Location $bootstrapDir
    git init
    git remote add origin $remoteUrl
    New-Item -ItemType File -Name ".gitkeep" -Value "" | Out-Null
    git add -A
    git commit -m "Initial empty gh-pages"
    git push origin HEAD:gh-pages
    Pop-Location
    Remove-Item -Recurse -Force $bootstrapDir

    git worktree add $worktreeDir gh-pages
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create worktree"
        exit 1
    }
}

Write-Host "Worktree ready at $worktreeDir"
```

### Step 5: Clear worktree and copy slideshow

```powershell
# Remove all existing files in worktree except .git
Get-ChildItem -Path $worktreeDir -Exclude ".git" | Remove-Item -Recurse -Force

# Copy slideshow files
Copy-Item -Recurse -Force "$staging\*" "$worktreeDir\"
Write-Host "  Copied slideshow to worktree"
```

### Step 6: Generate root landing page

```powershell
$landingPage = @'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Entry Tickets</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #000;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
        }
        h1 {
            font-size: 2.4em;
            color: #fff;
            margin-bottom: 12px;
        }
        p { color: #ccc; margin-bottom: 30px; font-size: 1.1em; }
        a {
            display: inline-block;
            background: #ffdd00;
            color: #000;
            padding: 14px 36px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 1.2em;
            font-weight: bold;
            transition: opacity 0.2s;
        }
        a:hover { opacity: 0.85; }
    </style>
</head>
<body>
    <h1>Entry Tickets</h1>
    <p>M2 / M3 Entry Ticket Slideshow</p>
    <a href="./">Open Slideshow</a>
</body>
</html>
'@

Set-Content -Path (Join-Path $worktreeDir "index.html") -Value $landingPage -NoNewline
Write-Host "  Generated landing page"
```

### Step 7: Commit and push from worktree

```powershell
$date = Get-Date -Format "ddMMyy"
git -C $worktreeDir add -A
git -C $worktreeDir commit -m "Deploy entry tickets ($date)"
git -C $worktreeDir push origin gh-pages
```

### Step 8: Clean up worktree

```powershell
git worktree remove $worktreeDir
Write-Host "Worktree removed. Still on main."
```

### Step 9: Print URL

```powershell
Write-Host ""
Write-Host "Deployed: entry-tickets"
Write-Host "  https://$owner.github.io/$repo/"
Write-Host ""
```

## Edge cases
- **First deploy (no gh-pages branch):** bootstrapped from an isolated `git init` in `%TEMP%` — never touches the main working tree
- **Subsequent deploy:** files in the worktree are cleared and replaced; landing page regenerated each time
- **gh not authenticated:** aborts with instruction
- **Worktree add fails:** exits with error; stale worktree cleaned up
- **Push fails:** worktree left on disk for manual recovery
