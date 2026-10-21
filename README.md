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
make up        # == docker compose up --build -d
```

После старта:

- Веб-интерфейс (TV + админка): `http://<IP-сервера>/` (порт 80, при доступности)
- API: `http://<IP-сервера>:8000`
- Swagger API: `http://<IP-сервера>:8000/docs`
- Логин по умолчанию: `admin` / `admin`

При первом запуске backend сам прогоняет миграции (`alembic upgrade head`),
сид (админ, тариф 300/час, 9 станций) и поднимается. Postgres доступен только
внутри compose-сети — наружу не проброшен.

**Продакшен (без домена, доступ по IP):**

1. Подготовить файл настроек сервера (в корне репозитория, Docker читает его
   автоматически):
   ```bash
   cp .env.example .env
   # обязательно смените ADMIN_PASSWORD, при желании задайте TELEGRAM_BOT_TOKEN
   ```
2. Проверить окружение (порты, версия compose, RAM, диск, сеть):
   ```bash
   make doctor
   ```
3. Запустить:
   ```bash
   docker compose up --build -d
   ```
4. Открыть `http://<IP-сервера>/`.

Полезное:

```bash
docker compose ps              # статус всех сервисов
docker compose logs -f         # логи
docker compose down            # остановить (данные в именованных volumes)
docker compose up --build -d   # пересобрать и запустить после изменений
```

Настройки сервера — в корневом `.env`: `HTTP_PORT` (по умолчанию `80`),
`API_PORT` (`8000`), `POSTGRES_PASSWORD`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`,
`JWT_SECRET`, `TELEGRAM_BOT_TOKEN`, `CORS_ORIGINS`, `CLUB_TIMEZONE` и др.
Файл `backend/.env` используется только для локальной разработки — Docker его
не читает.

`ADMIN_PASSWORD` из `.env` применяется **только при первой инициализации**
(когда админа ещё нет). Поменять пароль позже:

```bash
# 1) вписать новый пароль в .env (ADMIN_PASSWORD=...)
# 2) применить его
make admin-password        # == docker compose exec backend python -m app.seed --reset-password
```

JWT-секрет: если `JWT_SECRET` пуст, он генерируется один раз и хранится на
volume `backendsecrets` — токены админа переживают рестарт/пересборку. Данные
БД — на volume `pgdata`. Удаление `docker compose down -v` сотрёт и секрет, и
данные (потом нужен повторный логин).

### Если что-то не запускается

```bash
make doctor        # диагностика окружения
docker compose logs --tail=50 backend
docker compose ps  # все сервисы должны быть Up (backend — healthy)
```

Частые причины:

| Симптом | Причина | Решение |
|---|---|---|
| `port is already allocated` | порт 80/8000 занят | `HTTP_PORT=8080` в `.env` |
| `docker compose: command not found` | нет плагина Compose v2 | `sudo apt-get install docker-compose-plugin` |
| `services.backend.env_file must be a mapping` | слишком старый Compose | обновить Compose до v2.x |
| `cannot build: out of memory` / OOM | < 1 ГБ RAM | добавить swap или уменьшить нагрузку |
| `Seed complete` + `Application startup complete`, но сайт не открывается | закрыт firewall | `sudo ufw allow 80/tcp` |
| забыл пароль админа | — | `docker compose exec backend python -m app.seed --reset-password` |

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

Бот присылает уведомления и показывает состояние станций. Им может пользоваться
не только админ, но и клиент — каждый сам выбирает, о каких станциях получать
уведомления. Бот **не изменяет данные**: из него нельзя запускать, продлевать,
останавливать сессии или менять тарифы.

1. Создайте бота у [@BotFather](https://t.me/BotFather) и получите токен.
2. Укажите токен в `backend/.env`:
   ```env
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_POLL_INTERVAL=15
   ```
3. Перезапустите backend — бот стартует вместе с API (long polling, webhook не нужен).

Всё управление — кнопками (inline-клавиатура), команды не обязательны:

| Кнопка / команда | Действие |
|---|---|
| `/start` | меню + подписка (по умолчанию на все станции) |
| 📺 Станции | состояние станций и выбор подписки по кнопкам |
| 🔔 Подписки | текущая подписка, «Отключить все» |
| `/stations` | состояние всех станций |
| `/subs` | мои подписки |
| `/stop` | отключить все уведомления |
| `/help` | справка |

Как подписаться:

- На экране **📺 Станции** каждая станция — кнопка `✅`/`➕`: нажмите, чтобы
  включить или выключить уведомления по конкретной станции.
- Кнопка **«Все станции»** — подписка на всё сразу.
- **«🔕 Отключить все»** — мгновенно выключает уведомления.

Уведомления: старт сессии, пауза, продление, предупреждения (5/3/1 мин),
истечение времени, завершение сессии. Подписки хранятся в таблицах
`telegram_subscribers` и `telegram_station_subscriptions`; если пользователь
заблокировал бота, подписка автоматически отключается. Пустой
`TELEGRAM_BOT_TOKEN` полностью выключает бота.

## Бизнес-логика тарифов

- **FIXED**: цена = `price_per_hour / 60 × купленные минуты`.
- **OPEN**: точный расчёт посекундно — `price_per_hour / 3600 × прошедшие секунды`,
  округление только итоговой суммы до копейки. Тариф фиксируется снапшотом на
  момент старта сессии.
- Голосовые предупреждения (5/3/1 минута, окончание) гейтятся серверными
  флагами `warning_*_sent`, чтобы не повторяться после перезагрузки TV.

## Быстрые действия (отключение света)

Во вкладке **Обзор** есть блок «Отключение света — быстрые действия»:

- **Остановить все** — ставит на паузу все запущенные сессии (FIXED и OPEN).
- **Возобновить все** — снимает паузу со всех сессий.
- **Продлить всем** — добавляет всем активным **фиксированным** сессиям
  заданное число минут **бесплатно**: таймер сдвигается, но цена не меняется.
  Открытые (OPEN) сессии игнорируются.

Технически бесплатное продление пишется в `sessions.comp_seconds`, а
`fixed_session_price` вычитает и паузы (`total_paused_seconds`), и
компенсацию (`comp_seconds`) из оплачиваемого времени.

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/sessions/pause-all` | пауза всех сессий |
| POST | `/api/sessions/resume-all` | возобновление всех сессий |
| POST | `/api/sessions/extend-all` | бесплатное продление FIXED-сессий |

При подключённом Telegram-боте каждое массовое действие дополнительно рассылает
одно общее уведомление всем подписчикам («Все станции поставлены на паузу»,
«Все станции возобновлены», «Всем добавлено N мин, бесплатно»). Персональные
уведомления по каждой станции в этом случае не дублируются.

## Переменные окружения

См. `backend/.env.example`. Обязательно задайте `JWT_SECRET` (≥ 32 симв.)
и смените `ADMIN_PASSWORD` в проде. Аналитика/ретенция:
`CLUB_TIMEZONE` (локальная таймзона, по умолчанию `Asia/Bishkek`),
`HISTORY_RETENTION_DAYS` (по умолчанию `30`), `CLEANUP_INTERVAL_HOURS` (`6`).