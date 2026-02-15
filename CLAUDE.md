# [Project Name]

This file provides context for Claude Code to understand this project and enforce development standards.

## Development Workflow (MANDATORY)

### Git Branching Strategy
- **NEVER commit directly to `main`.** All changes must go through a Pull Request.
- Create a feature branch for every piece of work: `feature/{short-description}`
- Use `fix/{short-description}` for bug fixes, `docs/{short-description}` for documentation-only changes.
- Keep branches short-lived — merge within 1-2 sessions, don't let them drift.

### Pull Request Workflow
1. Create feature branch: `git checkout -b feature/{name}`
2. Make changes, commit frequently with descriptive messages
3. Push branch: `git push -u origin feature/{name}`
4. Create PR: `gh pr create --title "..." --body "..."`
5. CI must pass (GitHub Actions runs tests + build automatically)
6. Merge via PR (squash merge): `gh pr merge --squash`
7. Delete the branch after merge: `git branch -d feature/{name}`
8. Switch back to main and pull: `git checkout main && git pull`

### CI/CD
- GitHub Actions runs on every push and PR to `main` (`.github/workflows/ci.yml`)
- **Do NOT merge if CI is red.** Fix the failing tests first.
- Check CI status: `gh pr checks` or `gh run list`

### What Goes in a PR
- One logical change per PR (one feature, one bug fix, one refactor)
- PRs that touch multiple unrelated features are too large — split them up
- Always include a summary of what changed and why in the PR description

### Code Review
- When completing a major feature, use the `superpowers:requesting-code-review` skill
- Review your own diff before creating the PR: `git diff main...HEAD`

## Working Instructions

- **Start-of-session routine** - When the user greets you to start a session: (1) welcome them, (2) read project docs and git log to understand current state, (3) present a short list of suggested things to work on (pending tasks, backlog items, known issues, next features).
- **End-of-session routine** - When the user says goodbye or ends the session, automatically: (1) commit and push all code changes via PR if not already merged, (2) update documentation files with any changes, decisions, or progress made during the session.
- **Document key learnings** when discovering important technical insights or solutions.
- **Document architectural changes** when making or deciding on structural changes.
- **Keep documentation in sync** with code changes (README, CLAUDE.md, etc.).

## Project Overview

**Purpose:** [Brief description of what this project does]

**Tech Stack:** [Languages, frameworks, key libraries]

**Repository:** [GitHub URL]

## Project Structure

```
project/
├── src/              # Source code
├── tests/            # Test files
├── docs/             # Documentation
├── .github/
│   └── workflows/
│       └── ci.yml    # CI pipeline
├── CLAUDE.md         # This file
└── README.md         # Project README
```

## Key Files

| File | Purpose |
|------|---------|
| `src/...` | [Describe key source files] |
| `tests/...` | [Describe test organization] |

## Testing

**Run tests:** `[test command, e.g., npm test]`

**Test framework:** [Jest, pytest, etc.]

## Deployment

```bash
# [Deployment commands]
```

## Conventions

- [Code style conventions]
- [Naming conventions]
- [Commit message conventions]

## Key Learnings

[Document important technical insights and solutions as you discover them]

## Backlog

- [ ] [Future work items]
