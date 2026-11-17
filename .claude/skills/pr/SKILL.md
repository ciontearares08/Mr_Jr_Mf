---
name: pr
description: Write the pull request description for the current branch from the diff and the test output, in the format of .github/pull_request_template.md. Use when the user asks to open, write, draft or update a pull request.
---

# Write a pull request

1. Read `.github/pull_request_template.md`. Keep each heading and each labeled bullet exactly as the template has them.
2. Read the change with `git log main..HEAD --oneline` and `git diff main...HEAD`.
3. Find the task ID in the branch name, for example `S3-01`. If the Jira key is not known, ask the user. Do not invent one.
4. Run the check for each app that the diff touches: `make api-check`, `make web-check` or `make sim-check`. On the host, use the targets that end in `-docker`. Copy the real result line, for example `113 passed`, into "Results".
5. Fill the sections:
   - "What and why": 3 to 5 full sentences. The chapter owner copies them into the report, so write them for a reader who did not see the code.
   - "How I tested it": the commands that you ran, and the manual steps that the user did. If nobody did a manual step, write that.
   - "Results": the test output, numbers and API responses. Ask the user for screenshots of each visible change. You cannot make them.
   - "Edge cases and known issues": the unusual inputs that the tests cover, and what does not work or was not tested.
6. Tick a checklist box only if you saw the proof in this session. Leave "Status set to Review on the plan" for the user.
7. Show the draft to the user. Create the pull request with `gh pr create` only after the user agrees.

Rules:

- Do not add a "Generated with" line or a co-author line unless the user asks for it.
- Do not claim a test that did not run. If a check failed, show the failure.
- If the diff covers more than one task, tell the user and suggest a split.
