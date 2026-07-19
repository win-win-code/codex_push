#!/usr/bin/env python3
"""Send safe, one-way Codex notifications to a single Telegram chat."""

import json
import subprocess
import sys
import ctypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


TOKEN_SERVICE = "codex-telegram-bot-token"
CHAT_ID_SERVICE = "codex-telegram-chat-id"
KEYCHAIN_ACCOUNT = "codex"
MAX_INPUT_CHARS = 1_000_000
MAX_RESULT_CHARS = 1_500
HTTP_TIMEOUT_SECONDS = 5
TELEGRAM_API_ROOT = "https://api.telegram.org"
CORE_GRAPHICS = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
CORE_FOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
SCREEN_LOCKED_KEY = b"kCGSSessionScreenIsLocked"
UTF8_ENCODING = 0x08000100


def _log_error(message):
    # Keep logs deliberately generic: never include task data, URLs, or secrets.
    print(f"telegram_notify: {message}", file=sys.stderr)


def _read_keychain(service):
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                KEYCHAIN_ACCOUNT,
                "-s",
                service,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return None
    return value


def _read_screen_lock_state():
    """Read the lock flag from the current macOS graphical session."""
    try:
        graphics = ctypes.CDLL(CORE_GRAPHICS)
        foundation = ctypes.CDLL(CORE_FOUNDATION)
        graphics.CGSessionCopyCurrentDictionary.argtypes = []
        graphics.CGSessionCopyCurrentDictionary.restype = ctypes.c_void_p
        foundation.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        foundation.CFStringCreateWithCString.restype = ctypes.c_void_p
        foundation.CFDictionaryGetValue.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        foundation.CFDictionaryGetValue.restype = ctypes.c_void_p
        foundation.CFGetTypeID.argtypes = [ctypes.c_void_p]
        foundation.CFGetTypeID.restype = ctypes.c_ulong
        foundation.CFBooleanGetTypeID.argtypes = []
        foundation.CFBooleanGetTypeID.restype = ctypes.c_ulong
        foundation.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
        foundation.CFBooleanGetValue.restype = ctypes.c_bool
        foundation.CFRelease.argtypes = [ctypes.c_void_p]
        foundation.CFRelease.restype = None

        session = graphics.CGSessionCopyCurrentDictionary()
        if not session:
            return None
        key = foundation.CFStringCreateWithCString(
            None, SCREEN_LOCKED_KEY, UTF8_ENCODING
        )
        if not key:
            foundation.CFRelease(session)
            return None
        try:
            value = foundation.CFDictionaryGetValue(session, key)
            if not value or (
                foundation.CFGetTypeID(value) != foundation.CFBooleanGetTypeID()
            ):
                return None
            return bool(foundation.CFBooleanGetValue(value))
        finally:
            foundation.CFRelease(key)
            foundation.CFRelease(session)
    except (AttributeError, OSError, TypeError, ValueError, ctypes.ArgumentError):
        return None


def _screen_is_locked():
    """Return True only when macOS positively reports a locked screen."""
    return _read_screen_lock_state() is True


def _valid_token(token):
    if not isinstance(token, str) or len(token) > 200:
        return False
    parts = token.split(":")
    return (
        len(parts) == 2
        and parts[0].isdigit()
        and bool(parts[1])
        and all(char.isalnum() or char in "_-" for char in parts[1])
    )


def _valid_chat_id(chat_id):
    if not isinstance(chat_id, str) or not 1 <= len(chat_id) <= 32:
        return False
    digits = chat_id[1:] if chat_id.startswith("-") else chat_id
    return bool(digits) and digits.isdigit()


def _compact(value, limit):
    if not isinstance(value, str):
        return ""
    compacted = " ".join(value.split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 1].rstrip() + "…"


def _project_name(event):
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return "неизвестно"
    try:
        project = Path(cwd).name or Path(cwd).anchor or cwd
    except (OSError, ValueError):
        project = "неизвестно"
    return _compact(project, 100) or "неизвестно"


def _permission_action(event):
    tool_name = event.get("tool_name")
    if tool_name == "Bash":
        return "запуск команды"
    if tool_name in ("apply_patch", "Edit", "Write"):
        return "изменение файлов"
    if isinstance(tool_name, str) and tool_name.startswith("mcp__"):
        return "доступ ко внешнему инструменту"
    return "выполнение действия"


def _is_structured_turn_result(value):
    """Ignore Codex's internal JSON progress payloads."""
    if not isinstance(value, str) or value.lstrip()[:1] not in ("{", "["):
        return False
    try:
        payload = json.loads(value)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, (dict, list))


def build_message(event, test_mode=False):
    if test_mode:
        return "🔔 Тест Codex\n\nУведомления Telegram работают."

    if event.get("type") == "agent-turn-complete":
        last_message = event.get("last-assistant-message")
        if _is_structured_turn_result(last_message):
            return None
        result = _compact(last_message, MAX_RESULT_CHARS)
        if not result:
            return None
        return (
            "✅\n\n"
            f"{result}\n\n"
            f"Проект: {_project_name(event)}"
        )

    if event.get("hook_event_name") == "PermissionRequest":
        return (
            "🔔\n\n"
            f"Нужно подтверждение: {_permission_action(event)}.\n"
            "Откройте Codex для подтверждения.\n\n"
            f"Проект: {_project_name(event)}"
        )

    return None


def _read_event(arguments):
    if arguments == ["--test"]:
        return {}, True
    if len(arguments) > 1:
        raise ValueError("too many arguments")

    raw = arguments[0] if arguments else sys.stdin.read(MAX_INPUT_CHARS + 1)
    if not raw or len(raw) > MAX_INPUT_CHARS:
        raise ValueError("invalid input size")
    event = json.loads(raw)
    if not isinstance(event, dict):
        raise ValueError("input must be an object")
    return event, False


def _post_telegram(token, chat_id, text):
    url = f"{TELEGRAM_API_ROOT}/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")

    # Retry only explicit Telegram/server rejections. Ambiguous transport failures
    # are not retried because the first request may already have delivered a push.
    for attempt in range(2):
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=HTTP_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read(65_536).decode("utf-8"))
        except urllib.error.HTTPError as error:
            retryable = error.code == 429 or 500 <= error.code < 600
            if attempt == 0 and retryable:
                continue
            return False
        except (OSError, ValueError, json.JSONDecodeError):
            return False

        if isinstance(payload, dict) and payload.get("ok") is True:
            return True
        if attempt == 1:
            return False

    return False


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    try:
        event, test_mode = _read_event(arguments)
        message = build_message(event, test_mode=test_mode)
    except (ValueError, json.JSONDecodeError):
        _log_error("invalid input")
        return 0

    if message is None:
        return 0

    # Never send task notifications while the current macOS session is visible.
    # If macOS cannot confirm the status, preserve privacy and do not send.
    if not test_mode and not _screen_is_locked():
        return 0

    try:
        token = _read_keychain(TOKEN_SERVICE)
        chat_id = _read_keychain(CHAT_ID_SERVICE)
        if not _valid_token(token) or not _valid_chat_id(chat_id):
            _log_error("Keychain credentials are unavailable or invalid")
            return 0

        if not _post_telegram(token, chat_id, message):
            _log_error("Telegram request failed")
    except Exception:
        # A notifier must never change the outcome of the Codex event that called it.
        _log_error("notification failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
