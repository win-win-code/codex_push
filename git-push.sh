#!/bin/zsh
set -euo pipefail

if (( $# == 0 )); then
  print -u2 "Usage: COMMIT_MESSAGE='message' $0 <file> [<file> ...]"
  exit 2
fi

SCRIPT_DIR=${0:A:h}
cd "${SCRIPT_DIR}"

git status --short
git add -- "$@"
git commit -m "${COMMIT_MESSAGE:-Update}"
git push origin "$(git branch --show-current)"
