#!/bin/zsh
set -eu

SCRIPT_DIR=${0:A:h}
CODEX_DIR="${CODEX_HOME:-${HOME}/.codex}"
TARGET_SCRIPT="${CODEX_DIR}/telegram_notify.py"

mkdir -p "${CODEX_DIR}"
install -m 700 "${SCRIPT_DIR}/telegram_notify.py" "${TARGET_SCRIPT}"

printf "Enter Telegram Bot Token in the secure Keychain prompt.\n"
/usr/bin/security add-generic-password -U -a codex \
  -s codex-telegram-bot-token -w
printf "Enter Telegram chat_id in the secure Keychain prompt.\n"
/usr/bin/security add-generic-password -U -a codex \
  -s codex-telegram-chat-id -w

printf "\nInstalled: %s\n" "${TARGET_SCRIPT}"
printf "Add this top-level setting near the beginning of %s/config.toml:\n\n" "${CODEX_DIR}"
printf 'notify = ["/usr/bin/python3", "%s"]\n\n' "${TARGET_SCRIPT}"
printf "Then run: /usr/bin/python3 %s --test\n" "${TARGET_SCRIPT}"
