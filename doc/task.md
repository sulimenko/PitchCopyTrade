# AI task workflow

This repository uses AI Pipeline v8.

## Worker command

Run one task:

```bash
RUN_ONCE=1 bash $HOME/.codex/ai-pipeline/bin/watch-and-run-tasks.sh
```

Do not use legacy worker paths, repository-local worker scripts, old wrapper variables, or ad-hoc task runners.

## Queue branch

All task markdown files are created only in:

```text
ai-task-queue:doc/tasks/ready/*.md
```

The queue branch was created from `develop`. It is the only branch where active task files should be authored.

## Base branch

The default implementation base branch is:

```text
develop
```

`main` is not the worker base branch unless a task contract explicitly overrides it with human approval.

## Work branches

Worker branches use:

```text
ai/T-XXX-short-title
```

Branch title must be short: task number plus 1-2 words. Examples:

```text
ai/T-001-db-mode
ai/T-002-clean-file-mode
ai/T-003-tbank-hardening
```

## Task IDs

Start new v8 tasks from:

```text
T-001
```

Before creating the next task, inspect existing task files in:

```text
doc/tasks/ready
doc/tasks/in-progress
doc/tasks/review
doc/tasks/done
doc/tasks/failed
```

Use the next incremental `T-XXX`. Follow-ups use suffixes such as `T-001A`, `T-001B` and continue the parent branch.

## Task contract

Only this block name is valid:

```text
ai-task-contract
```

`pbull-task-contract` is forbidden.

Every task must contain exactly one `ai-task-contract` block.

## Language

Task markdown, clarification questions, review conclusions, follow-up tasks and acceptance criteria must be written in Russian.

## Current architecture priority

The active runtime target is `APP_DATA_MODE=db` with PostgreSQL.

`APP_DATA_MODE=file`, `storage/seed/*`, JSON-backed file repositories, local demo seed flows and old file-mode parity work are legacy/compatibility areas. New tasks should not extend them unless the task explicitly says to remove, migrate or clean that legacy path.

## Clean queue commands

Use these commands when old active task files must be removed before adopting v8 rules.

```bash
git switch ai-task-queue
git pull --ff-only origin ai-task-queue

mkdir -p doc/tasks/ready doc/tasks/in-progress doc/tasks/review doc/tasks/done doc/tasks/failed

find doc/tasks/ready doc/tasks/in-progress doc/tasks/review doc/tasks/failed \
  -maxdepth 1 -type f -name "T-*.md" -print

# Archive a short log manually in doc/changelog.md before deleting old active tasks.
rm -f doc/tasks/ready/T-*.md
rm -f doc/tasks/in-progress/T-*.md
rm -f doc/tasks/review/T-*.md
rm -f doc/tasks/failed/T-*.md

rm -rf doc/ai/runs/*
rm -rf doc/ai/context/*
rm -rf doc/ai/review/*
rm -f diff.patch diff-stat.txt CHATGPT_REVIEW_REQUEST.md commits.txt status.txt

git add -A
git commit -m "chore(ai): clear active task queue"
git push origin ai-task-queue
```

If using zsh and glob errors appear, use `(N)` glob qualifiers or `find -delete`.

## Done queue

Do not delete completed task history unless explicitly asked. New tasks should inspect `done` to choose the next task number.

## Production work branch restrictions

Normal worker branches must not contain:

```text
doc/tasks/**
doc/ai/runs/**
doc/ai/context/**
doc/ai/review/**
diff.patch
diff-stat.txt
CHATGPT_REVIEW_REQUEST.md
commits.txt
status.txt
```

The worker may read `doc/ai/chatgpt/*.md` and `doc/ai/project-checks.sh`, but production PRs should not edit AI workflow documentation unless the task is explicitly an AI workflow documentation task.
