import contextlib
import io
import json
import sys
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import telegram_notify as notifier


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, _limit):
        return self.payload


class MessageTests(unittest.TestCase):
    @mock.patch.object(notifier, "_current_time", return_value="19:42")
    def test_completion_uses_only_safe_fields_and_truncates_result(self, _time):
        secret_prompt = "do not include this user prompt"
        message = notifier.build_message(
            {
                "type": "agent-turn-complete",
                "cwd": "/Users/me/projects/cvjn",
                "input-messages": [secret_prompt],
                "last-assistant-message": "x" * 1_700,
            }
        )

        self.assertIn("✅ Codex завершил задачу", message)
        self.assertIn("Проект: cvjn", message)
        self.assertIn("Время: 19:42", message)
        self.assertNotIn(secret_prompt, message)
        result = message.split("Результат: ", 1)[1].split("\nВремя:", 1)[0]
        self.assertEqual(len(result), notifier.MAX_RESULT_CHARS)
        self.assertTrue(result.endswith("…"))

    def test_permission_request_is_ignored(self):
        self.assertIsNone(
            notifier.build_message(
            {
                "hook_event_name": "PermissionRequest",
                "cwd": "/tmp/cvjn",
                "tool_name": "Bash",
                "tool_input": {"command": "curl -H 'Authorization: secret-token'"},
            }
            )
        )

    def test_manual_test_message(self):
        self.assertEqual(
            notifier.build_message({}, test_mode=True),
            "🔔 Тест Codex\n\nУведомления Telegram работают.",
        )

    def test_unknown_event_is_ignored(self):
        self.assertIsNone(notifier.build_message({"type": "something-else"}))


class TelegramTests(unittest.TestCase):
    @mock.patch.object(notifier.urllib.request, "urlopen")
    def test_post_uses_fixed_host_post_and_expected_payload(self, urlopen):
        urlopen.return_value = FakeResponse({"ok": True})

        sent = notifier._post_telegram(
            "123456:ABC_def-9", "-100123456", "hello"
        )

        self.assertTrue(sent)
        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://api.telegram.org/bot123456:ABC_def-9/sendMessage",
        )
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)
        self.assertEqual(
            urllib.parse.parse_qs(request.data.decode("utf-8")),
            {"chat_id": ["-100123456"], "text": ["hello"]},
        )

    @mock.patch.object(notifier.urllib.request, "urlopen")
    def test_retries_once_after_explicit_server_failure(self, urlopen):
        urlopen.side_effect = [
            urllib.error.HTTPError("safe-test-url", 500, "error", {}, None),
            FakeResponse({"ok": True}),
        ]

        self.assertTrue(notifier._post_telegram("1:abc", "123", "hello"))
        self.assertEqual(urlopen.call_count, 2)

    @mock.patch.object(notifier.urllib.request, "urlopen")
    def test_invalid_success_payload_fails_without_crashing(self, urlopen):
        urlopen.return_value = FakeResponse(["unexpected"])

        self.assertFalse(notifier._post_telegram("1:abc", "123", "hello"))
        self.assertEqual(urlopen.call_count, 2)

    @mock.patch.object(notifier.urllib.request, "urlopen")
    def test_does_not_retry_ambiguous_transport_failure(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("offline")

        self.assertFalse(notifier._post_telegram("1:abc", "123", "hello"))
        self.assertEqual(urlopen.call_count, 1)

    def test_main_never_leaks_event_or_token_on_send_failure(self):
        event = json.dumps(
            {
                "type": "agent-turn-complete",
                "cwd": "/tmp/project",
                "last-assistant-message": "private task result",
            }
        )
        stderr = io.StringIO()
        with (
            mock.patch.object(
                notifier,
                "_read_keychain",
                side_effect=["123456:very-secret-token", "123456789"],
            ),
            mock.patch.object(notifier, "_post_telegram", return_value=False),
            contextlib.redirect_stderr(stderr),
        ):
            result = notifier.main([event])

        self.assertEqual(result, 0)
        self.assertNotIn("private task result", stderr.getvalue())
        self.assertNotIn("very-secret-token", stderr.getvalue())

    def test_invalid_input_still_exits_zero(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(notifier.main(["not-json"]), 0)


if __name__ == "__main__":
    unittest.main()
