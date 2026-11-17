---
name: migration
description: Add or repair an Alembic database migration in apps/api. Use after a change to a SQLAlchemy model, when CI reports more than one Alembic head, when alembic check fails, or when the user asks for a migration.
---

# Add a database migration

Run these commands in the API devcontainer. They need `uv` and a running database.

## New migration

1. Change the model in `apps/api/src/api/db/models`. If the model is new, import it in `db/models/__init__.py`.
2. Run `make migrate`, so that the database is at the current head.
3. Run `make migration m="describe the change"`.
4. Read the new file in `apps/api/alembic/versions`. Autogenerate misses some changes, so make sure that the file has these:
   - a server default or a data step for each new column that is `nullable=False` on a table with rows
   - each check constraint and each renamed column, because autogenerate reads a rename as a drop and an add
   - a `downgrade()` that undoes each step of `upgrade()` in reverse order
   - no operation on `spatial_ref_sys` or on the PostGIS tiger and topology tables
5. Run `make migrate`, then `make migrate-down`, then `make migrate` again. All three must pass.
6. Run `make migrate-check`. It must print `No new upgrade operations detected.`
7. Run `make api-test`.

## Two heads

Two branches that each add a migration give two heads after a merge.

1. Run `cd apps/api && uv run alembic heads` to list them.
2. If your migration is not on `main` yet, change its `down_revision` to the head from `main`. This keeps the history in one line.
3. If both migrations are on `main`, run `uv run alembic merge heads -m "merge <a> and <b>"`.
4. Run `make migrate` and `make migrate-check`.

## Rules

- Do not edit a migration that is on `main`. Add a new one.
- Do not run `make db-reset`, `make db-fresh` or `make db-nuke` unless the user asks. They delete data.
- If a schema that the API returns changed, the `api-change` skill has the next steps.
