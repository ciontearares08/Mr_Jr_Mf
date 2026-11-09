# Agricultural Simulation project
This codebase was written for AAU MsC Computer Engineering 4th groups group project

# IMPORTANT !!!
Before the first start, copy `example.env` to `.env` in the repo root and set `JWT_SECRET_KEY`. The API will not start without it.

After pulling run these commands:
1. `docker compose up -d db` to pull the new image
2. `make api-setup` (installs deps and runs the migrations)
The docker image for the db has changed so these commands are mandatory


# Layout
The project has three main parts, all three are stored in apps directory:
## Web
This is where the react frontend lives

The frontend uses these main libraries for its work:
- React + Vite - Used for the app and dev server
- Tailwind + shadcn - Used for styling and UI components
- React Router - Used for page routing
- Leaflet + Geoman - Used for the field map and drawing field boundaries
- Recharts - Used for charts
- 
## API
This is where the backend lives

The backend uses these main libraries for its work:
- FastAPI - Used for the actual API routing work
- SQLAlchemy - Used for defining database models
- Pydantic - Used for defining API requests and data returned
- Alembic - Used to create migrations for the models defined with SQLAlchemy
- GeoAlchemy2, Shapely, pyproj - Used for field boundaries and mapping fields to DMI grid cells
- httpx - Used to download weather data from DMI

## Sim
This is where the APSIM simulation service lives

It runs the APSIM wheat model in `models/wheat.apsimx` and returns one row per day of the season. It calls APSIM's own `Models` program directly, so apsimNGpy is not used.
APSIM is installed in the APSIM devcontainer.

## Database
PostgreSQL with PostGIS, runs as the `db` service in docker compose on port 5432

## Common commands

Run `make` in the repo root to list every command. These are the ones you'll use most:

- `make api-setup` installs the API dependencies and applies migrations `make web-setup` installs the web dependencies. Run both after pulling. `make sim-setup` installs the sim dependencies. Run them after pulling.
- `make api-dev` starts the API on port 8000, `make web-dev` starts the web app on port 5173, and make sim-dev` starts the sim service on port 8001.
- `make migration m="describe the change"` generates a migration from your model changes, and `make migrate` applies it, and `make migrate-down` rolls back the latest one.

- `make api-check` and `make web-check` run the same checks as CI. `make sim-check` runs the sim lint and tests.
- `make api-types` regenerates the frontend API types from the running API.

Run API commands in the API devcontainer, Web commands in the Web devcontainer, and Sim command in the Sim devcontainer

A pre-commit hook lints the files you stage. To skip it for one commit, run `git commit --no-verify`.

On Windows without WSL you won't have `make`. Run `docker compose up` on the host, then run `make` inside the devcontainers. Run `uv` commands only inside the devcontainers, not on Windows.
