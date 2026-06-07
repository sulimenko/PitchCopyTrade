# Reviewer instructions

Review AI worker output for PitchCopyTrade.

Use Russian for conclusions and follow-up tasks.

## Read first

- `doc/ai/chatgpt/project-settings.md`
- `doc/blueprint.md`
- `doc/task.md`
- `README.md`

## Output

Use:

```text
Approved with notes
```

or:

```text
Blocked
```

When blocked, name files and reasons.

## Required checks

- work targets `develop`;
- work branch follows `ai/T-XXX-short-title`;
- normal work branch does not include task queue files;
- normal work branch does not include local AI artifacts;
- task contract uses `ai-task-contract` only;
- default runtime target stays `APP_DATA_MODE=db`;
- legacy file mode is not expanded unless the task explicitly says so;
- subscriber UX remains Telegram-first and Mini App-first;
- staff, admin, author and moderator remain staff web surfaces;
- author work remains message-centric through `/author/messages`;
- visible UI text is Russian.

## Validation

Default command:

```bash
BASE_BRANCH=develop CHECK_MODE=default bash doc/ai/project-checks.sh
```

DB/runtime command:

```bash
BASE_BRANCH=develop CHECK_MODE=db bash doc/ai/project-checks.sh
```
