#!/bin/sh
# Runs after Claude Code edits or writes a file. Formats Python files of the api and
# sim apps with ruff, and repairs web files with ESLint. A tool that is not installed
# in the current environment is skipped, as in .githooks/pre-commit. It never blocks
# an edit: CI and the make check targets report what is left.

root=${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}
[ -n "$root" ] || exit 0

# The hook input is JSON on stdin. The edited path is in tool_input.file_path.
input=$(cat)
if command -v python3 >/dev/null 2>&1; then
  file=$(printf '%s' "$input" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))' 2>/dev/null)
elif command -v node >/dev/null 2>&1; then
  file=$(printf '%s' "$input" | node -e 'let s = ""; process.stdin.on("data", (d) => (s += d)).on("end", () => console.log(JSON.parse(s).tool_input?.file_path ?? ""))' 2>/dev/null)
else
  exit 0
fi
[ -f "$file" ] || exit 0

case "$file" in
  "$root"/apps/api/*.py) app=api ;;
  "$root"/apps/sim/*.py) app=sim ;;
  "$root"/apps/web/src/components/ui/*) exit 0 ;; # shadcn generates these files
  "$root"/apps/web/*.ts | "$root"/apps/web/*.tsx) app=web ;;
  *) exit 0 ;;
esac

if [ "$app" = web ]; then
  eslint="$root/apps/web/node_modules/.bin/eslint"
  [ -x "$eslint" ] && (cd "$root/apps/web" && "$eslint" --fix "$file" >/dev/null 2>&1)
else
  ruff="$root/apps/$app/.venv/bin/ruff"
  if [ -x "$ruff" ]; then
    # Only sorts imports. A full --fix deletes an import that the next edit will use.
    (cd "$root/apps/$app" && "$ruff" check --select I --fix --quiet "$file" >/dev/null 2>&1
      "$ruff" format --quiet "$file" >/dev/null 2>&1)
  fi
fi
exit 0
