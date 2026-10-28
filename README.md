# Менеджер задач: тесты, Docker и CI/CD

![CI](https://github.com/crasavella04/python-lab7/actions/workflows/ci.yml/badge.svg)

Практическая работа №3. За основу взят REST API из практической работы №2 (FastAPI + PostgreSQL +
SQLAlchemy 2.0 async + Alembic). В этой работе к нему добавлены:

- автотесты (15 штук) на **pytest + httpx**, они работают с настоящим PostgreSQL;
- многоэтапный **Dockerfile**, приложение в контейнере запускается не от root;
- **docker-compose.yml** с сервисами БД, миграций, приложения и тестов;
- **GitHub Actions**: lint и test на каждый push и pull request, сборка и публикация образа в GHCR и Docker Hub при push в `main`.

## Опубликованные образы

| Реестр | Ссылка | Как скачать |
|---|---|---|
| GitHub Container Registry | https://github.com/crasavella04/python-lab7/pkgs/container/python-lab7 | `docker pull ghcr.io/crasavella04/python-lab7:latest` |
| Docker Hub | https://hub.docker.com/r/crasavella/python-lab7 | `docker pull crasavella/python-lab7:latest` |

У каждого образа два тега: `latest` и `sha-<короткий хеш коммита>`.

## Структура проекта

```
.
├── app/                      # приложение из ПР №2
├── migrations/               # Alembic
├── tests/
│   ├── conftest.py           # тестовая БД, очистка таблиц, dependency_overrides, клиент
│   ├── test_users.py
│   └── test_tasks.py
├── .github/workflows/ci.yml  # lint → test → build
├── Dockerfile                # builder / builder-dev / test / runtime
├── docker-compose.yml        # db + migrate + app (+ tests)
├── requirements.txt
├── requirements-dev.txt      # pytest, pytest-asyncio, httpx, ruff
├── pytest.ini
└── ruff.toml
```

## Тесты

Тесты работают с отдельной базой `tasks_test`. Перед каждым тестом таблицы очищаются (`TRUNCATE ... RESTART IDENTITY`).
Зависимость `get_session` подменяется через `app.dependency_overrides`, чтобы приложение брало сессии из тестовой БД.
Если базы `tasks_test` ещё нет, фикстура создаёт её сама, а схему строит из моделей.

| № | Тест | Что проверяет |
|---|---|---|
| 1 | `test_create_user` | создание пользователя → 201 |
| 2 | `test_create_user_duplicate_email` | повторный email → 409 |
| 3 | `test_create_user_invalid_email` | невалидный email → 422 |
| 4 | `test_create_task` | создание задачи → 201 |
| 5 | `test_create_task_unknown_owner` | несуществующий владелец → 404 |
| 6 | `test_list_tasks_filter_done_and_pagination` | фильтр `done`, `limit`/`offset` и их сочетание |
| 7 | `test_patch_updates_only_passed_fields` | PATCH меняет только переданные поля, изменение сохраняется в БД |
| 8 | `test_delete_then_get_returns_404` | DELETE → 204, затем GET → 404 |
| 9 | `test_process_time_header` | в ответе есть заголовок `X-Process-Time` |
| + | `test_get_user`, `test_get_user_not_found`, `test_create_task_empty_title`, `test_list_tasks_invalid_limit`, `test_patch_null_title_rejected`, `test_delete_unknown_task` | дополнительные проверки 200/404/422 |

### Локальный запуск

Нужны Python 3.12 и PostgreSQL. Проще всего поднять PostgreSQL из compose:

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

docker compose up -d db         # PostgreSQL на localhost:5432

pytest -v                       # по умолчанию TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/tasks_test
ruff check . && ruff format --check .
```

Если PostgreSQL уже работает в другом месте, адрес тестовой базы задаётся переменной окружения `TEST_DATABASE_URL`.

### Запуск через Docker Compose

```bash
docker compose run --rm --build tests   # поднимет db, дождётся healthcheck и запустит pytest -v в контейнере
docker compose down
```

## Docker

**Dockerfile** собирается в несколько этапов:

| Этап | Что делает |
|---|---|
| `builder` | создаёт venv `/opt/venv` и ставит туда `requirements.txt` |
| `builder-dev` | ставит туда же `requirements-dev.txt` |
| `test` | чистый `python:3.12-slim`, venv из `builder-dev` и весь код вместе с тестами |
| `runtime` (по умолчанию) | чистый `python:3.12-slim`, venv из `builder` и только `app/`, `migrations/`, `alembic.ini` |

В финальные образы не попадают pip-кеш, тесты, `.git` и `.env`. Процесс работает от системного пользователя `app` (uid 10001), не от root.

**docker-compose.yml**:

- `db`: `postgres:16` с healthcheck через `pg_isready`;
- `migrate`: одноразовый контейнер из образа приложения, выполняет `alembic upgrade head` и завершается. Ждёт `db: service_healthy`;
- `app`: uvicorn на `:8000`. Стартует только когда `db` здорова и `migrate` завершился успешно (`service_completed_successfully`);
- `tests`: образ этапа `test` в профиле `test`. Обычный `up` его не запускает.

```bash
docker compose up -d --build    # БД → миграции → приложение
# Swagger UI: http://localhost:8000/docs
docker compose logs migrate     # вывод alembic
docker compose down             # добавьте -v, чтобы удалить и данные БД
```

## CI/CD (GitHub Actions)

Workflow `.github/workflows/ci.yml`:

```
push / pull_request ─┬─ lint  (ruff check, ruff format --check)
                     └─ test  (service-контейнер postgres:16 → alembic upgrade head → pytest -v)
                            │
                needs: [lint, test], только push в main
                            ▼
                         build  (docker buildx → ghcr.io/crasavella04/python-lab7
                                              → docker.io/crasavella/python-lab7)
```

- В GHCR вход выполняется через встроенный `GITHUB_TOKEN`. Job `build` получает право `packages: write`.
- Для Docker Hub в настройках репозитория (*Settings → Secrets and variables → Actions*) заведены:
  - переменная `DOCKERHUB_USERNAME` (логин Docker Hub);
  - секрет `DOCKERHUB_TOKEN` (Personal Access Token с правами Read & Write, создаётся в *Docker Hub → Account settings → Personal access tokens*).
- Слои кешируются в GitHub Actions cache (`cache-from/to: type=gha`).

### Проверка pipeline (шаг 8)

1. Ветка `broken-test`: в `test_create_user` ожидаемый код специально изменён на 200. В [PR #1](https://github.com/crasavella04/python-lab7/pull/1) pipeline красный: `test` падает, `build` пропущен.
2. Тест исправлен в той же ветке, pipeline зелёный, PR влит в `main`. После merge все три job-а прошли, `build` опубликовал образ.

**Успешный pipeline (push в `main` после merge):**

![Успешный pipeline](screenshots/ci_success.png)

**«Упавший» pipeline (PR с намеренно сломанным тестом):**

![Упавший pipeline](screenshots/ci_failed.png)

**PR #1: коммит со сломанным тестом ❌, коммит с исправлением ✅:**

![PR #1](screenshots/ci_pr.png)

## Ответы на контрольные вопросы

**1. Чем CI отличается от CD (continuous delivery и continuous deployment)?**

*Continuous Integration*: каждое изменение часто вливается в общую ветку, и на каждый push или PR автоматически запускаются
сборка, линтер и тесты. Цель CI в том, чтобы ошибка интеграции находилась за минуты, а не перед релизом.
*Continuous Delivery* продолжает CI: каждое изменение, прошедшее pipeline, автоматически собирается в готовый к выпуску артефакт
(здесь это Docker-образ в реестре) и может уйти в прод в любой момент. Сам выпуск при этом запускает человек.
*Continuous Deployment* убирает и этот ручной шаг: всё, что прошло pipeline, автоматически разворачивается в production.
Разница между двумя CD только в том, есть ли ручное подтверждение перед выкладкой. В этой работе реализованы CI и
continuous delivery: образ публикуется автоматически, а развёртывания нет.

**2. Как работает `dependency_overrides` и зачем он нужен в тестах?**

`app.dependency_overrides` — это словарь `{исходная_зависимость: замена}`. Когда FastAPI разрешает `Depends(get_session)`,
он сначала ищет функцию в этом словаре и, если находит, вызывает замену. Код эндпоинтов при этом не меняется.
В тестах так подменяется `get_session`: приложение получает сессии к тестовой БД `tasks_test`, а не к рабочей.
Так же можно подставить фейковую авторизацию, внешний сервис или мок. После теста словарь очищается
(`app.dependency_overrides.clear()`), чтобы подмены не протекали в другие тесты.

**3. Зачем нужна многоэтапная сборка образа?**

Сборка разделяется на этапы, и в финальный образ копируется только результат (`COPY --from=builder`).
Компиляторы, pip-кеш, dev-зависимости (pytest, ruff) и исходники тестов остаются в промежуточных этапах.
Поэтому финальный образ меньше (быстрее скачивается и разворачивается), в нём меньше пакетов и уязвимостей.
Кроме того, из одного Dockerfile получаются разные цели: здесь `runtime` для продакшена и `test` для запуска тестов.
Плюс отдельные этапы лучше кешируются: если зависимости не менялись, при изменении кода слой с ними пересобирать не нужно.

**4. Почему контейнер не следует запускать от root?**

Root внутри контейнера по умолчанию совпадает с root на хосте (uid 0), его ограничивают только namespaces, capabilities
и seccomp. Если в приложении найдут RCE или если сработает уязвимость в runtime/ядре, позволяющая выйти из контейнера,
атакующий сразу получит максимальные права. От root он может менять файлы в смонтированных томах, ставить пакеты,
открывать привилегированные порты и пробовать эскалацию через ядро. Непривилегированный пользователь соблюдает принцип
минимальных привилегий: даже взломанный процесс не может изменить код приложения в образе и сильно ограничен в действиях.
Многие платформы (Kubernetes с `runAsNonRoot`, OpenShift) вообще не запускают контейнеры от root.

**5. Как в GitHub Actions передаются секреты и почему их нельзя хранить в репозитории?**

Секреты задаются в *Settings → Secrets and variables → Actions* на уровне репозитория, окружения или организации и хранятся в
зашифрованном виде. В workflow к ним обращаются через `${{ secrets.NAME }}`, обычно передают в `with:` или `env:` шага.
GitHub маскирует их значения в логах (`***`) и не передаёт workflow, запущенным из PR форков. Встроенный `GITHUB_TOKEN`
выдаётся автоматически на время одного запуска, а его права задаются в `permissions:`.
Хранить секреты в репозитории нельзя: их видит каждый, у кого есть доступ к коду (а у публичного репозитория — весь
интернет). Они навсегда остаются в истории git, даже если файл потом удалить. Они попадают в форки, клоны, кеши и бэкапы,
а боты непрерывно сканируют GitHub в поисках токенов. Утёкший секрет приходится срочно отзывать и перевыпускать.

**6. Что произойдёт с job-ом `build`, если упадёт `test`? Где это задаётся?**

Job `build` не запустится: он получит статус *skipped*, и образ не будет собран и опубликован. Это задаётся ключом
`needs: [lint, test]` у job-а `build` в `ci.yml`. По умолчанию зависимый job выполняется, только если все job-ы из `needs`
завершились успешно (неявное условие `success()`). Дополнительно `build` ограничен условием
`if: github.event_name == 'push' && github.ref == 'refs/heads/main'`, поэтому в pull request он не запускается совсем.

**7. Где лучше применять миграции: при старте контейнера или отдельным шагом в CD? Плюсы и минусы.**

*При старте контейнера* (`alembic upgrade head && uvicorn ...` в entrypoint):
- плюсы: просто, ничего не нужно настраивать отдельно, схема гарантированно соответствует коду, удобно для разработки и маленьких проектов;
- минусы: при нескольких репликах миграции запускаются параллельно и могут конфликтовать (нужны блокировки);
  долгая миграция задерживает старт и может провалить healthcheck; приложению нужны права на DDL; ошибка миграции
  уводит контейнер в цикл перезапусков; откат кода не откатывает схему.

*Отдельным шагом в CD* (job или одноразовый контейнер перед выкладкой):
- плюсы: миграция выполняется ровно один раз и контролируемо; при ошибке выкладка останавливается до обновления
  приложения; у приложения могут быть права только на DML; логи и статус миграции видны отдельно;
  можно добавить ручное подтверждение для опасных изменений;
- минусы: сложнее pipeline, CD нужен сетевой доступ к БД и секреты; между миграцией и выкладкой старая версия кода
  работает с новой схемой, поэтому миграции должны быть обратно совместимыми (expand → migrate → contract).

Для продакшена обычно выбирают отдельный шаг. В этом проекте сделан компромисс: в `docker-compose.yml` миграции выполняет
отдельный одноразовый сервис `migrate`, а `app` стартует только после его успешного завершения.
