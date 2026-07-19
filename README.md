# codex_push

## Telegram-уведомления Codex

Минимальный one-way бот для macOS. Скрипт запускается только на событиях Codex, делает POST в Telegram и завершается. Фонового сервиса, polling и запросов к модели нет.

Уведомления о событиях отправляются только когда системный флаг macOS
`IOConsoleLocked` равен `Yes`. При разблокированном или неопределённом состоянии
событие молча пропускается. Проверка работает из фонового hook Codex и не
зависит от GUI-сессии процесса.

## Что отправляется

- `agent-turn-complete`: последний ответ Codex до 1 500 символов и имя проекта;
- `PermissionRequest`: запрос подтверждения действия с именем проекта;
- `--test`: только тестовый текст.

Ввод пользователя, логи, содержимое файлов и параметры команд не отправляются.

## Установка

1. Создайте бота через `@BotFather`, откройте чат с ним и нажмите **Start**.
2. Получите `chat_id`. В терминале введите token скрыто, затем найдите
   `result[].message.chat.id` в ответе:

   ```bash
   read -s TOKEN
   curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates"
   unset TOKEN
   ```

   Для группы `chat_id` обычно отрицательный. Не публикуйте token и не
   сохраняйте его в файлах проекта.
3. Запустите инсталлятор и введите token и `chat_id` в терминале:

   ```bash
   ./install.sh
   ```

   Он установит скрипт как `~/.codex/telegram_notify.py` с правами `700`, а секреты запишет в macOS Keychain под account `codex` и services:

   - `codex-telegram-bot-token`;
   - `codex-telegram-chat-id`.

4. Настройте глобальный `~/.codex/config.toml`, только если top-level ключ
   `notify` ещё не задан. Готовый фрагмент есть в `config.example.toml`:

   ```toml
   notify = ["/usr/bin/python3", "/Users/USERNAME/.codex/telegram_notify.py"]
   ```

   `notify` должен быть top-level ключом: разместите его до первой TOML-таблицы. В проектном `.codex/config.toml` он игнорируется.

   Если `notify` уже настроен — например, через системные уведомления или
   fanout — не заменяйте его этой строкой. Сохраните действующую команду и
   добавьте `~/.codex/telegram_notify.py` в её цепочку. При повторном запуске
   `./install.sh` менять `config.toml` не требуется.

5. Проверьте token и `chat_id`:

   ```bash
   /usr/bin/python3 ~/.codex/telegram_notify.py --test
   ```

   `--test` всегда отправляет сообщение — он не проверяет блокировку экрана.
   Для проверки фильтра отправьте короткое сообщение Codex: при разблокированном
   Mac пуша быть не должно. Затем заблокируйте Mac (`Control` + `Command` +
   `Q`) до завершения следующего ответа — пуш должен прийти.

   Текущее состояние можно посмотреть так:

   ```bash
   /usr/sbin/ioreg -p IOService -d 0 -l | grep IOConsoleLocked
   ```

   `Yes` означает заблокированный экран, `No` — разблокированный.

Ошибка Keychain или Telegram пишет только общую строку в `stderr`, не раскрывая token или текст задачи. Код возврата скрипта всегда `0`, поэтому сбой уведомления не блокирует Codex.

## Проверка

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

Скрипт использует только стандартную библиотеку Python.
