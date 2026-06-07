# Task T-XXX: short title

```ai-task-contract
version: 1
task_id: T-XXX
type: primary
human_summary: "Короткое описание задачи"
execution_mode: codex-simple

git:
  base_branch: develop
  queue_branch: ai-task-queue
  parent_branch: none
  work_branch: ai/T-XXX-short
  work_branch_policy: create_task_branch
  allow_new_branch: true
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
  message: "feat(ai): implement T-XXX short"
```

## Task routing

Task type: primary  
Base branch: develop  
Parent task: none  
Parent branch: none  
Work branch policy: create-task-branch  
Queue branch: ai-task-queue

## Execution mode

codex-simple

## Цель

Опиши цель.

## Контекст

Опиши контекст.

## Affected files

- `path/to/file.ext`

## Expected fix areas

- Опиши ожидаемые области изменений.

## Constraints

- Не менять `.env`, secrets, credentials, tokens.
- Не добавлять dependencies без отдельного approval.
- Не делать unrelated refactoring.
- Не менять production config без отдельного approval.
- Не коммитить `doc/tasks/**` и local AI artifacts в рабочую ветку.
- Не расширять legacy `APP_DATA_MODE=file`, если задача прямо не требует его удаления или миграции.

## Validation commands

```bash
BASE_BRANCH=develop CHECK_MODE=default bash doc/ai/project-checks.sh
```

## Acceptance criteria

- Критерий 1.
- Критерий 2.
