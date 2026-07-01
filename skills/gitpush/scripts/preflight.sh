#!/usr/bin/env bash
# Gathers git repo state for the gitpush skill so prehook questions can be
# answered from real data rather than guesses. Emits KEY=VALUE lines.
# Never mutates the repo. Safe to run repeatedly.
set -uo pipefail

emit() { printf '%s=%s\n' "$1" "$2"; }

# --- Is this a git repo? ---
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  emit IS_GIT_REPO false
  exit 0
fi
emit IS_GIT_REPO true

# --- Current branch ---
CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo 'DETACHED')"
emit CURRENT_BRANCH "$CURRENT_BRANCH"

# --- All local branches (comma-separated) ---
LOCAL_BRANCHES="$(git for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null | paste -sd, -)"
emit LOCAL_BRANCHES "${LOCAL_BRANCHES:-}"

# --- Remote 'origin' ---
ORIGIN_URL="$(git remote get-url origin 2>/dev/null)"
if [ -z "$ORIGIN_URL" ]; then
  emit HAS_ORIGIN false
  emit ORIGIN_URL ""
else
  emit HAS_ORIGIN true
  emit ORIGIN_URL "$ORIGIN_URL"
fi

# --- Working tree cleanliness ---
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  emit WORKTREE_DIRTY true
  emit UNCOMMITTED_COUNT "$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
else
  emit WORKTREE_DIRTY false
  emit UNCOMMITTED_COUNT 0
fi

# --- Fetch latest refs (read-only against remote) so ahead/behind is accurate ---
if [ "${ORIGIN_URL:-}" != "" ]; then
  if git fetch --quiet origin >/dev/null 2>&1; then
    emit FETCH_OK true
  else
    emit FETCH_OK false
  fi

  # Determine the remote default branch (usually main or master)
  DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
  if [ -z "$DEFAULT_BRANCH" ]; then
    if git show-ref --verify --quiet refs/remotes/origin/main; then DEFAULT_BRANCH=main
    elif git show-ref --verify --quiet refs/remotes/origin/master; then DEFAULT_BRANCH=master
    fi
  fi
  emit DEFAULT_BRANCH "${DEFAULT_BRANCH:-}"

  # Ahead/behind of the CURRENT branch vs its own upstream (if any)
  UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"
  if [ -n "$UPSTREAM" ]; then
    emit UPSTREAM "$UPSTREAM"
    set -- $(git rev-list --left-right --count "${UPSTREAM}...HEAD" 2>/dev/null)
    emit BEHIND_UPSTREAM "${1:-0}"
    emit AHEAD_UPSTREAM "${2:-0}"
  else
    emit UPSTREAM ""
    emit BEHIND_UPSTREAM 0
    emit AHEAD_UPSTREAM 0
  fi

  # Ahead/behind of the CURRENT branch vs origin/<default> (the "in sync with origin main" check)
  if [ -n "${DEFAULT_BRANCH:-}" ] && git show-ref --verify --quiet "refs/remotes/origin/${DEFAULT_BRANCH}"; then
    set -- $(git rev-list --left-right --count "origin/${DEFAULT_BRANCH}...HEAD" 2>/dev/null)
    emit BEHIND_DEFAULT "${1:-0}"
    emit AHEAD_DEFAULT "${2:-0}"
  else
    emit BEHIND_DEFAULT unknown
    emit AHEAD_DEFAULT unknown
  fi
fi
