# Agent guide

This file tells coding agents how to work in this repo. `CLAUDE.md` imports it, so Claude Code and other agents read the same rules. The system is not finished. If this file and the code disagree, trust the code and correct this file in the same pull request.

## Layout

| Path | Content |
| :--- | :--- |
| `apps/api` | FastAPI backend with SQLAlchemy models, Pydantic schemas and Alembic migrations |
| `apps/web` | React and Vite frontend in TypeScript, with Tailwind and shadcn components |
| `apps/sim` | FastAPI service that runs the APSIM wheat model |
| `compose.yaml` | The three apps and the PostGIS database |
| `Makefile` | Every command. Run `make` to list the targets. |

## Where commands run

Each app has its own devcontainer, and the tools of one app are not installed in the others. `uv` is in the API and APSIM containers. `npm` is in the Web container. APSIM is only in the APSIM container.

If you work on the host machine, use the Docker targets. They need Docker and a `.env` file in the repo root.

| In the devcontainer | On the host | What it runs |
| :--- | :--- | :--- |
| `make api-check` | `make api-check-docker` | ruff, pyright, the migration check and pytest |
| `make web-check` | `make web-check-docker` | ESLint, tsc, Vitest and the build |
| `make sim-check` | `make sim-check-docker` | ruff, pyright and pytest with APSIM |

Run the check of each app that you changed before you say that the work is complete. To run one test, use `make api-test args="-k name -x"`. To repair most ruff errors, run `make api-format` or `make sim-format`.

## API rules

- Models are in `src/api/db/models`, schemas in `src/api/schemas`, and routes in `src/api/routers`. Register each new model in `db/models/__init__.py`, or Alembic does not see it.
- After a model change, run `make migration m="describe the change"`, then read the generated file. Do not edit a migration that is on `main`.
- Exactly one Alembic head must exist. After you merge `main` into your branch, run `make migrate-check`. If it reports two heads, run `uv run alembic merge heads -m "merge <a> and <b>"` in `apps/api`.
- Each migration must have a working `downgrade()`. CI runs `downgrade base` and then `upgrade head`.
- After a change to a schema or a route, regenerate `apps/web/src/shared/api-types.ts` with `make api-types`. If the file is out of date, CI fails. Never edit that file by hand.
- Use `require_role()` from `api/auth/permissions.py` for field access. A user who is not a member gets 404, not 403.
- Tests use the `db` and `client` fixtures in `tests/conftest.py`. Each test runs in a transaction that rolls back, so tests need a migrated database and leave no rows.
- Tests must never call DMI. The `--block-network` option enforces this. To record a cassette (a saved HTTP response), follow the note at the top of `tests/test_dmi.py`, and record one test at a time.
- `db-seed`, `db-fresh`, `db-reset` and `db-nuke` change or delete data. Do not run them unless the user asks.

## Web rules

- shadcn generates `src/components/ui`. Do not edit those files by hand. Add a component with the shadcn CLI.
- Import with the `@/` alias, for example `@/components/Navbar`.
- Take API types from `@/shared/api-types`, as `src/services/fieldData.ts` does. Do not write a second copy of a response type.
- Read the base URL from `API_URL` in `src/services/config.ts`.
- Put a test next to the file that it tests, with the name `<file>.test.ts`. `src/services/fieldData.test.ts` is the example.

## Sim rules

- `run_season()` in `src/sim/apsim.py` runs `models/wheat.apsimx`. `models/README.md` describes the model, the report columns and the soil limits. If you change the model, update that file.
- The API reads `apps/sim/models/stages.json`. If you rename a stage, run the API tests too.
- The tests need APSIM, so they only run in the APSIM container or through `make sim-check-docker`.

## Stub data and FAKE comments

`apps/api/src/api/routers/stubs.py` returns example data until the real routes exist. Every invented value has a comment that starts with `FAKE:` and names the task that replaces it. Keep this rule for new stub values. When the value becomes real, remove the comment.

## Tasks, branches, commits and pull requests

- A task ID has the form `S<sprint>-<number>`, for example `S3-01`. The Jira key has the form `SCRUM-<number>`.
- Name the branch after the task, for example `S3-01-fields-api`. Never commit to `main`.
- A commit message has at most two sentences and no bullet list. The detail goes in the pull request.
- A pull request follows `.github/pull_request_template.md` exactly. "What and why" has 3 to 5 sentences, because the chapter owner copies them into the report.
- Keep one task in one pull request. Do not mix a refactor into a feature.

## Do not change without a request

- `.env` and secrets. `example.env` is the template.
- Dependency versions and lockfiles that the task does not need.
- Files that the task does not mention. Leave their style problems for a separate pull request.
