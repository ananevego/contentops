# ContentOps

ContentOps — сервис автоматизации работы с трендовым контентом. Telegram-бот получает запросы пользователя, собирает данные TikTok через Apify, сохраняет и ранжирует контент в PostgreSQL, а затем использует OpenRouter и PubMed API для генерации и проверки черновиков публикаций.

## Архитектура

```mermaid
flowchart TB
    User[Пользователь Telegram] <-->|long polling| Bot[ContentOps bot\nPython-контейнер]

    Bot -->|SQLAlchemy| DB[(PostgreSQL 16)]
    DB --- Volume[(postgres_data\nименованный Docker volume)]

    Bot -->|Telegram Bot API| Relay[Cloudflare Worker\nTelegram Relay]
    Relay -->|HTTPS| Telegram[Telegram Bot API]

    Bot -->|TikTok-метаданные, OCR, транскрипции| Apify[Apify API]
    Bot -->|идеи, посты, анализ релевантности| OpenRouter[OpenRouter API]
    Bot -->|поиск научных публикаций| PubMed[NCBI PubMed API]

    Dev[Git push] --> CI[GitHub Actions]
    CI -->|pytest| Tests[Тесты]
    CI -->|build & push| GHCR[GitHub Container Registry]
    GHCR -->|image pull| Bot
```

Архитектура состоит из одного прикладного контейнера и отдельного контейнера базы данных. Взаимодействие между ними происходит внутри сети Docker Compose: приложение обращается к БД по DNS-имени `postgres`, а не по опубликованному порту хоста. Внешние интеграции доступны только через исходящие запросы из контейнера приложения.

Для production-доступа к Telegram Bot API используется Cloudflare Worker как relay. Это связано с тем, что из Yandex Cloud VM прямое TCP-соединение с `api.telegram.org:443` оказалось недоступным, несмотря на наличие рабочего исходящего Интернет-соединения. Worker принимает запрос от приложения, проверяет секретный заголовок и перенаправляет запрос в Telegram Bot API.

В локальной разработке relay не требуется: если переменные `TELEGRAM_RELAY_URL` и `RELAY_SECRET` не заданы, приложение обращается к Telegram Bot API напрямую.

## Сервисы

### `bot`

Основной сервис запускается из Docker-образа командой `python -m app.telegram.bot`. Он использует библиотеку `python-telegram-bot` и получает обновления Telegram методом long polling. Поэтому для работы не нужен публичный HTTP-вход, webhook, домен или TLS-терминация: контейнер сам устанавливает исходящее соединение к Telegram API.

В production исходящие запросы к Telegram проходят через Cloudflare Worker relay. URL relay и секрет передаются приложению через переменные окружения:

* `TELEGRAM_RELAY_URL` — URL Cloudflare Worker;
* `RELAY_SECRET` — секрет для аутентификации запросов к Worker.

Relay включается только если обе переменные заданы. Благодаря этому один и тот же Docker-образ используется и локально, и в production:

```text
Локальная разработка:

ContentOps → Telegram Bot API


Production:

ContentOps → Cloudflare Worker → Telegram Bot API
```

При старте бот:

1. Создаёт отсутствующие таблицы в PostgreSQL через SQLAlchemy.
2. Проверяет наличие `TELEGRAM_BOT_TOKEN`.
3. Проверяет наличие production relay-конфигурации, если она задана.
4. Регистрирует обработчики команд, callback-кнопок и текстовых сообщений.
5. Запускает polling-цикл.

Сервис использует `restart: unless-stopped`. Docker перезапустит его после аварийного завершения или перезагрузки хоста, кроме случая, когда оператор остановил контейнер явно.

### `Cloudflare Worker Telegram Relay`

Cloudflare Worker используется как промежуточный HTTPS relay между production-контейнером ContentOps и Telegram Bot API.

Worker:

1. Получает HTTP-запрос от ContentOps.
2. Проверяет заголовок `X-Relay-Secret`.
3. Сравнивает его со значением `RELAY_SECRET`, хранящимся в секретах Worker.
4. При успешной проверке перенаправляет запрос на соответствующий endpoint `api.telegram.org`.
5. Возвращает ответ Telegram обратно приложению.

Секрет relay не хранится в исходном коде и не попадает в Docker image. На production VM он хранится в `.env`, который не отслеживается Git.

Таким образом, production-запрос выглядит следующим образом:

```text
ContentOps container
        │
        │ HTTPS
        │ X-Relay-Secret
        ▼
Cloudflare Worker
        │
        │ HTTPS
        ▼
api.telegram.org
```

Cloudflare Worker не заменяет Telegram Bot API и не хранит Telegram Bot Token. Он используется только как контролируемая точка маршрутизации исходящих запросов.

### `postgres`

Используется официальный образ `postgres:16`. База хранит:

* собранные элементы контента и рассчитанные оценки тренда;
* настройки пользователей Telegram;
* историю видео, уже использованных для создания постов.

Данные расположены в именованном томе `postgres_data`, смонтированном в `/var/lib/postgresql/data`. Поэтому пересоздание контейнера PostgreSQL не удаляет данные.

У БД настроен healthcheck `pg_isready`. Сервис `bot` содержит зависимость `depends_on` с условием `service_healthy`: запуск бота откладывается, пока PostgreSQL не начнёт принимать подключения. Это исключает типичную race condition, когда приложение стартует раньше БД.

В development-конфигурации порт PostgreSQL опубликован как `5432:5432` для локальной диагностики. В production-конфигурации секция `ports` отсутствует: база доступна только другим контейнерам внутренней сети Compose и не открыта в сеть хоста.

### FastAPI

В пакете присутствует FastAPI-приложение с маршрутами `/`, `/health`, `/hello` и `/config`. Endpoint `/health` возвращает статус `ok` и имя сервиса; он покрыт тестом.

Сейчас Compose запускает Telegram-бота, а не ASGI-сервер. Поэтому FastAPI-интерфейс является отдельным компонентом кода, но не отдельным production-сервисом в текущей схеме развёртывания.

## Поток данных приложения

1. Пользователь выбирает действие в Telegram-боте.
2. Коллекторы запрашивают TikTok-данные через Apify. Для обычного видео извлекается транскрипция; для слайд-шоу — OCR-текст изображений.
3. Нормализатор преобразует ответ внешнего API во внутреннюю модель `ContentItem`.
4. Репозиторий проверяет `external_id`. Если такой элемент уже есть в PostgreSQL, повторная запись не создаётся.
5. Модуль аналитики рассчитывает `trend_score` из просмотров, лайков, комментариев, репостов и возраста публикации.
6. Бот выдаёт ранжированные тренды. При необходимости генератор запрашивает у OpenRouter идею или текст поста.
7. Для фактчекинга модуль research получает публикации из PubMed, анализирует утверждения и может сформировать доработанную версию поста.

## Контейнеризация

`Dockerfile` использует базовый образ `python:3.13.5-slim`, задаёт рабочую директорию `/app`, копирует `requirements.txt` и пакет `app`, устанавливает зависимости и запускает Telegram-бота.

`.dockerignore` исключает из контекста сборки виртуальные окружения, `.env`, кэши, каталоги Git и Python-артефакты. Это уменьшает размер контекста и предотвращает попадание локальных секретов в Docker-образ.

Для стека предусмотрены два Compose-файла:

| Файл                      | Назначение           | Отличия                                                                                                                                            |
| ------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docker-compose.yml`      | Локальная разработка | Собирает `bot` из исходников, монтирует каталог проекта и открывает порт PostgreSQL на хосте. Включён Compose watch для пересборки при изменениях. |
| `docker-compose.prod.yml` | Развёртывание        | Использует опубликованный образ `ghcr.io/ananevego/contentops:latest`, не монтирует исходный код и не публикует порт базы данных.                  |

Production-конфигурация также передаёт `TELEGRAM_RELAY_URL` и `RELAY_SECRET` через `.env`. Локальная конфигурация может не содержать эти переменные: в таком случае relay автоматически отключён.

## Конфигурация и секреты

Секреты передаются приложению через файл окружения `.env`, указанный в Compose как `env_file`. Сам файл не отслеживается Git и не передаётся в контекст Docker build.

| Группа переменных                                   | Назначение                                                             |
| --------------------------------------------------- | ---------------------------------------------------------------------- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Инициализация PostgreSQL и строка подключения приложения.              |
| `POSTGRES_HOST`, `POSTGRES_PORT`                    | Адрес БД. В Compose используется `postgres:5432`.                      |
| `TELEGRAM_BOT_TOKEN`                                | Аутентификация Telegram-бота.                                          |
| `TELEGRAM_RELAY_URL`                                | URL Cloudflare Worker relay для production-доступа к Telegram Bot API. |
| `RELAY_SECRET`                                      | Секрет для аутентификации запросов ContentOps к Cloudflare Worker.     |
| `APIFY_TOKEN`                                       | Доступ к TikTok-коллекторам, транскрипции и OCR.                       |
| `OPENROUTER_API_KEY`                                | Генерация идей и постов, LLM-анализ.                                   |
| `NCBI_EMAIL`, `NCBI_API_KEY`                        | Запросы к PubMed/NCBI для фактчекинга.                                 |
| `APP_NAME`, `ENVIRONMENT`                           | Метаданные, возвращаемые маршрутом FastAPI `/config`.                  |

В production секреты должны находиться в защищённом окружении хоста или внешнем менеджере секретов. Они не должны попадать в Dockerfile, Compose-файлы, логи или историю Git.

`RELAY_SECRET` хранится в двух местах:

* в Cloudflare Worker как Secret;
* на production VM в `.env`.

Значение секрета не встраивается в исходный код или Docker image.

## CI/CD

GitHub Actions настроен в [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Workflow запускается на каждый `push` и работает в следующей последовательности:

```text
push → checkout → Python 3.13 → pip install → pytest
     → login в ghcr.io через GITHUB_TOKEN
     → Docker build → push образа
```

После успешного `pytest` workflow публикует образ в GitHub Container Registry с двумя тегами:

* `ghcr.io/ananevego/contentops:latest` — последняя успешная сборка;
* `ghcr.io/ananevego/contentops:<SHA коммита>` — неизменяемая версия конкретного коммита.

SHA-тег нужен для воспроизводимого развёртывания и отката: он позволяет запустить строго тот образ, который был собран из определённой версии исходного кода, без зависимости от изменяемого `latest`.

Production VM получает новый образ из GHCR и запускает его через `docker-compose.prod.yml`. Секреты и production-конфигурация при этом остаются на VM и не входят в CI/CD artifact.

## Проверки

Тесты находятся в каталоге `tests/` и запускаются в CI перед публикацией образа. Они проверяют ответы FastAPI, загрузку конфигурации, модели данных, нормализацию TikTok-данных и требования к редакторскому стилю генератора.
