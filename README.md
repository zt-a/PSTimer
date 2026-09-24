# PS Timer — PlayStation Club Management

Управление PlayStation-клубом: таймеры сессий, тарифы, стенды, голосовые
предупреждения на TV-дашборде, админ-панель.

- **Backend**: FastAPI, SQLAlchemy 2 (async), PostgreSQL, Alembic, JWT + Argon2, WebSocket
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Framer Motion, Zustand, React Query, Recharts
- **TV-дашборд** обновляется по WebSocket `/ws/dashboard`, голос через Web Speech API (ru-RU)
- **Аналитика и история**: выручка, сессии, средний чек, загрузка, графики, чеки,
  ретенция истории и фоновый воркер очистки

## Быстрый старт (Docker)

```bash
cp backend/.env.example backend/.env   # при необходимости задать JWT_SECRET
make up
```

После старта:

- ТВ-дашборд: http://localhost:5173
- Админ-панель: http://localhost:5173/admin (по умолчанию `admin` / `admin`)
- Swagger API: http://localhost:8000/docs

При первом запуске контейнер backend сам прогоняет `alembic upgrade head`
и сид-данные (админ, дефолтный тариф 300/час, 10 станций).

## Локальная разработка (без Docker)

Требуется PostgreSQL (в Docker):

```bash
docker run -d --name pstimer-db \
  -e POSTGRES_USER=pstimer -e POSTGRES_PASSWORD=pstimer -e POSTGRES_DB=pstimer \
  -p 5432:5432 postgres:17-alpine
```

Backend:

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Vite проксирует `/api` и `/ws` на `localhost:8000`.

## Тесты

```bash
cd backend && . .venv/bin/activate && pytest -q
```

Покрытие: биллинг и округление, auth, CRUD станций/тарифов,
жизненный цикл FIXED и OPEN сессий, публичный дашборд, аналитика и ретенция,
Telegram-подписки и уведомления.

## Аналитика, история и чеки

В админ-панели есть вкладки **Аналитика** и **История**:

- **Аналитика** — период (день/неделя/месяц/год/произвольный), KPI (выручка,
  сессии, средний чек, отыграно, загрузка) с динамикой к прошлому периоду,
  графики выручки и сессий, разбивка по станциям и тарифам, тепловая карта
  загруженности по дням недели и часам.
- **История** — постраничный список сессий (фильтры по станции и статусу) и
  история оплат; по каждой записи открывается чек с возможностью печати.

Эндпоинты (все под `get_current_admin`):

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/reports/summary` | KPI за период (+ динамика) |
| GET | `/api/reports/revenue` | временной ряд выручки/сессий |
| GET | `/api/reports/stations` | разбивка по станциям |
| GET | `/api/reports/tariffs` | разбивка по тарифам |
| GET | `/api/reports/heatmap` | выручка по дням недели/часам |
| GET | `/api/reports/sessions` | история сессий (пагинация) |
| GET | `/api/reports/sessions/{id}` | чек по сессии |
| GET | `/api/reports/payments` | история оплат |
| POST | `/api/reports/cleanup` | ручная очистка истории |

Параметры: `period=today|week|month|year|all` **или** `date_from`/`date_to`
(`YYYY-MM-DD`), а также `station_id`, `status`, `page`, `page_size`.
Границы дня считаются в локальной таймзоне клуба (`CLUB_TIMEZONE`).

## Ретенция истории (воркер)

Сырая история сессий хранится не дольше `HISTORY_RETENTION_DAYS` (по умолчанию
**30 дней**). Отдельный воркер периодически удаляет завершённые сессии и их
транзакции старше этого срока:

```bash
# локально
cd backend && . .venv/bin/activate
python -m app.worker          # цикл (интервал CLEANUP_INTERVAL_HOURS)
python -m app.worker --once   # один проход (для cron/теста)
```

В Docker воркер запускается отдельным сервисом `worker` (`docker compose up`).
Активные/открытые сессии никогда не удаляются.

### Демо-данные

```bash
cd backend && . .venv/bin/activate
python -m app.seed_demo --clear --days 35   # ~35 дней реалистичной истории
```

## Telegram-бот (только чтение)

Админ работает с телефона, поэтому бот шлёт уведомления и позволяет смотреть
состояние станций. Бот **не изменяет данные**: из него нельзя запускать,
продлевать, останавливать сессии или менять тарифы.

1. Создайте бота у [@BotFather](https://t.me/BotFather) и получите токен.
2. Укажите токен в `backend/.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_POLL_INTERVAL=15
   ```
3. Перезапустите backend — бот стартует вместе с API (long polling, webhook не нужен).

Команды:

| Команда | Действие |
|---|---|
| `/start` | подписаться на уведомления |
| `/stations` | показать состояние всех станций |
| `/stop` | отписаться от уведомлений |
| `/help` | справка |

Уведомления: старт сессии, пауза, продление, предупреждения (5/3/1 мин),
истечение времени, завершение сессии. Подписчики хранятся в таблице
`telegram_subscribers`; если пользователь заблокировал бота, подписка
автоматически отключается. Пустой `TELEGRAM_BOT_TOKEN` полностью выключает бота.

## Бизнес-логика тарифов

- **FIXED**: цена = `price_per_hour / 60 × купленные минуты`.
- **OPEN**: точный расчёт посекундно — `price_per_hour / 3600 × прошедшие секунды`,
  округление только итоговой суммы до копейки. Тариф фиксируется снапшотом на
  момент старта сессии.
- Голосовые предупреждения (5/3/1 минута, окончание) гейтятся серверными
  флагами `warning_*_sent`, чтобы не повторяться после перезагрузки TV.

## Переменные окружения

См. `backend/.env.example`. Обязательно задайте `JWT_SECRET` (≥ 32 симв.)
и смените `ADMIN_PASSWORD` в проде. Аналитика/ретенция:
`CLUB_TIMEZONE` (локальная таймзона, по умолчанию `Asia/Bishkek`),
`HISTORY_RETENTION_DAYS` (по умолчанию `30`), `CLEANUP_INTERVAL_HOURS` (`6`).