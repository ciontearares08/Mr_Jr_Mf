# Agricultural Simulation project
This codebase was written for AAU MsC Computer Engineering 4th groups group project

# IMPORTANT !!!
After pulling run these commands:
1. `docker compose up -d db` to pull the new image
2. `make api-setup` (installs deps and runs the migrations)
The docker image for the db has changed so these commands are mandatory

# Layout
The project has two main parts, both are stored in apps directory:
## Web
This is where the react frontend lives
## API
This is where the backend lives

The backend uses these main libraries for its work:
- FastAPI - Used for the actual API routing work
- SQLAlchemy - Used for defining database models
- Pydantic - Used for defining API requests and data returned
- Alembic - Used to create migrations for the models defined with SQLAlchemy

## Common commands

Run `make` in the repo root to list every command. These are the ones you'll use most:

- `make api-setup` installs the API dependencies and applies migrations. `make web-setup` installs the web dependencies. Run both after pulling.
- `make api-dev` starts the API on port 8000, and `make web-dev` starts the web app on port 5173.
- `make migration m="describe the change"` generates a migration from your model changes, and `make migrate` applies it.
- `make api-check` and `make web-check` run the same checks as CI.

Run API commands in the API devcontainer and web commands in the Web devcontainer.

A pre-commit hook lints the files you stage. To skip it for one commit, run `git commit --no-verify`.

On Windows without WSL you won't have `make`. Run `docker compose up` on the host, then run `make` inside the devcontainers.

## Baseline Wheat Model (`wheat.apsimx`)

This directory contains the base simulation templates utilized by the `sim` API service.

**Model Specification:**
- **APSIM Version:** 2024.6.7516.0
- **Cultivar:** [Insert Cultivar Name, e.g., Scout]
- **Sowing Date:** 15-Oct (Baseline - dynamically overridden by API)
- **Soil Type:** [Insert Soil Name, e.g., Silt Loam]
- **Source Paper/Validation:** [Insert Paper DOI/Title that produced zealand_cleaned.csv]

## Soil Hydraulic Limits (Constant Parameters)
The following limits define the water holding characteristics across the soil profile layers:

| Layer | Depth (cm) | LL15 (Lower Limit) | DUL (Drained Upper Limit) | SAT (Saturation) |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0 - 15 | [Insert Value] | [Insert Value] | [Insert Value] |
| 2 | 15 - 30 | [Insert Value] | [Insert Value] | [Insert Value] |
| 3 | 30 - 60 | [Insert Value] | [Insert Value] | [Insert Value] |
| 4 | 60 - 90 | [Insert Value] | [Insert Value] | [Insert Value] |
