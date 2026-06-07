# Task T-XXXA: short follow-up

```ai-task-contract
version: 1
task_id: T-XXXA
type: follow-up
human_summary: "Короткое описание follow-up"
execution_mode: codex-simple

git:
  base_branch: develop
  queue_branch: ai-task-queue
  parent_branch: ai/T-XXX-short
  work_branch: ai/T-XXX-short
  work_branch_policy: continue_parent_branch
  allow_new_branch: false
  allow_codex_git: false

scope:
  allowed_files:
    - path/to/file.ext
  forbidden_files:
    - doc/tasks/**
    - doc/ai/runs/**
    - doc/ai/context/**
    - doc/ai/review/**
    - .env
    - .env.*
    - deploy/**
    - pyproject.toml

validation:
  commands:
    - BASE_BRANCH=develop CHECK_MODE=default bash doc/ai/project-checks.sh

diff_budget:
  max_files_changed: 5
  max_added_lines: 300
  max_deleted_lines: 120

commit:
  message: "fix(ai): implement T-XXXA follow-up"
```

## Task routing

Task type: follow-up  
Base branch: develop  
Parent task: T-XXX  
Parent branch: ai/T-XXX-short  
Work branch policy: use-parent-branch  
Queue branch: ai-task-queue

## Execution mode

codex-simple

## Причина follow-up

Опиши реальный gap после review.

## Цель

Опиши цель.

## Affected files

- `path/to/file.ext`

## Expected fix areas

- Опиши изменения.

## Constraints

- Не расширять scope без необходимости.
- Не коммитить AI workflow artifacts.
- Не расширять legacy file mode, если follow-up не про его удаление или миграцию.

## Validation commands

```bash
BASE_BRANCH=develop CHECK_MODE=default bash doc/ai/project-checks.sh
```

## Acceptance criteria

- Критерий 1.
- Критерий 2.
