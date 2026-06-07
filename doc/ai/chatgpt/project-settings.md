# AI project settings

Repository: `sulimenko/PitchCopyTrade`.

AI Pipeline version: v8.

Worker command:

```bash
RUN_ONCE=1 bash $HOME/.codex/ai-pipeline/bin/watch-and-run-tasks.sh
```

Branches:

- base branch: `develop`
- queue branch: `ai-task-queue`
- work branch format: `ai/T-XXX-short-title`

Task IDs start from `T-001`.

Task files are created only in:

```text
doc/tasks/ready/*.md
```

Task contract block name:

```text
ai-task-contract
```

`pbull-task-contract` is forbidden.

All task text, review text and acceptance criteria must be written in Russian.

Active runtime target: `APP_DATA_MODE=db`.

Legacy areas: `APP_DATA_MODE=file`, JSON file repositories, `storage/seed/*`, `storage/runtime/*`.

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
