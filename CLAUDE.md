@AGENTS.md

## Claude Code

Project skills are in `.claude/skills`:

- `pr` writes a pull request description.
- `migration` adds or repairs a database migration.
- `api-change` covers a change to a route or a schema, from the model to the web app.

`.claude/settings.json` allows the `make` check targets without a prompt. After each edit, a hook runs ruff or ESLint on the file. If the tool is not installed where you work, the hook does nothing.
