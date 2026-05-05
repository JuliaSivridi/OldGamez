# oldgamez_bot

Единый Telegram-бот для мини-игр.

## Что уже заложено

- один бот и одна точка входа
- Docker Compose для бота и PostgreSQL
- SQLAlchemy-модели для пользователей, игровых сессий и статистики
- структура проекта, где каждая игра живет в своем модуле

## Запуск в Docker

1. Скопировать `.env.example` в `.env`
2. Указать `BOT_TOKEN`
3. Запустить:

```bash
docker compose up --build
```

## Почему PostgreSQL в Docker

PostgreSQL не нужно устанавливать на сервер вручную, если на сервере есть Docker. База поднимается отдельным контейнером через `docker compose`.

## Локальный запуск без Docker

Можно использовать SQLite, если поменять `DATABASE_URL`, например:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/local.db
```

Тогда приложение можно запустить локально:

```bash
python -m app.main
```

## Идея архитектуры

- `app/main.py` - точка входа
- `app/handlers/` - команды и роутинг Telegram
- `app/games/` - отдельные игровые модули
- `app/services/` - бизнес-логика
- `app/db/` - модели и подключение к БД

