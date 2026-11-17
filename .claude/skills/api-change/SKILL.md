---
name: api-change
description: Add or change an API route or a response schema and carry the change through to the web app. Use for a new endpoint, a changed Pydantic schema, a stub route that becomes real, or when the API types CI job fails.
---

# Change an API route or schema

Do the steps in this order. Each step depends on the one before it.

1. Model. If the data is stored, change the model in `apps/api/src/api/db/models` and follow the `migration` skill.
2. Schema. Add or change the Pydantic model in `apps/api/src/api/schemas`. Give each field a `description`, because it becomes the text in `/docs` and in the web types.
3. Route. Add the route in `apps/api/src/api/routers` and set `response_model`. A new router must be included in `apps/api/src/api/main.py`. For field access, call `require_role()` from `api/auth/permissions.py`.
4. Test. Add a test in `apps/api/tests` with the `client` and `db` fixtures. Cover a success, a wrong input, and a user without access.
5. Check. Run `make api-check`, or `make api-check-docker` on the host.
6. Types. Regenerate `apps/web/src/shared/api-types.ts`:
   - in the Web devcontainer, with the API running: `make api-types`
   - without a running API: `make api-openapi` where `uv` is installed, then `OPENAPI_URL=openapi.json npm run api-types` in `apps/web` where `npm` is installed
7. Web. Export the type and add the fetch function in `apps/web/src/services/fieldData.ts`. Do not write the response type by hand.
8. Check. Run `make web-check`, or `make web-check-docker` on the host.

When a stub route in `routers/stubs.py` becomes real, keep the response model, move the path to `/fields/{id}/...`, and delete each `FAKE:` comment for a value that is now real.

Commit the regenerated `api-types.ts` in the same pull request as the API change. The "API types" CI job compares the two.
