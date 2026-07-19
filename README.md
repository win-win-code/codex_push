# Telegram-уведомления Codex

Минимальный one-way бот для macOS. Скрипт запускается только на событиях Codex, делает POST в Telegram и завершается. Фонового сервиса, polling и запросов к модели нет.

## Что отправляется

- `agent-turn-complete`: имя проекта, последний ответ Codex до 1 500 символов и время;
- `PermissionRequest`: имя проекта и безопасная категория действия без параметров команды;
- `--test`: только тестовый текст.

Ввод пользователя, логи, содержимое файлов и параметры команд не отправляются.

## Установка

1. Создайте бота через `@BotFather`, откройте его и нажмите **Start**.
2. Получите `chat_id` из Telegram `getUpdates`. Не публикуйте token и не сохраняйте его в файлах проекта.
3. Запустите инсталлятор и введите token и `chat_id` в терминале:

   ```bash
   ./install.sh
   ```

   Он установит скрипт как `~/.codex/telegram_notify.py` с правами `700`, а секреты запишет в macOS Keychain под account `codex` и services:

   - `codex-telegram-bot-token`;
   - `codex-telegram-chat-id`.

4. Добавьте выведенные инсталлятором строки в глобальный `~/.codex/config.toml`. Готовый шаблон есть в `config.example.toml`.

   `notify` должен быть top-level ключом: разместите его до первой TOML-таблицы. В проектном `.codex/config.toml` он игнорируется.

5. Перезапустите Codex. В CLI откройте `/hooks`, проверьте и доверьте hook.
6. Отправьте тест:

   ```bash
   /usr/bin/python3 ~/.codex/telegram_notify.py --test
   ```

Ошибка Keychain или Telegram пишет только общую строку в `stderr`, не раскрывая token или текст задачи. Код возврата скрипта всегда `0`, поэтому сбой уведомления не блокирует Codex.

## Проверка

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

Скрипт использует только стандартную библиотеку Python.
