---
description: Deploy the entry ticket slideshow to GitHub Pages via gh-pages branch. Creates the branch on first run, updates on subsequent runs.
---

# Command: Git Pages

## Usage
`/git-pages`

Deploys `slides/index.html` (and its `assets/`) to `https://elwrush.github.io/entry-tickets/`.

**First run:** creates the `gh-pages` branch and deploys.
**Subsequent runs:** overwrites existing files and pushes.

## What it does
1. Copies the slideshow to a staging temp directory
2. Creates/updates a `git worktree` for `gh-pages` in a separate temp directory (never switches branch in main working tree)
3. Copies files into the worktree
4. Generates a root `index.html` landing page
5. Commits and pushes from the worktree
6. Removes the worktree
7. Prints the URL

## Safety
**This command NEVER switches branches in the main working tree.** All gh-pages operations happen inside a `git worktree`. If anything fails, the main project directory is untouched.
