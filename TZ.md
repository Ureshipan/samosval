## Техническое задание (ТЗ)

### Информационная система “Самосвал” (CI/CD оркестратор — имитация)

## 1. Назначение и общая концепция

ИС “Самосвал” предназначена для автоматизации процесса развёртывания приложений разработчиков на ресурсах компании через веб‑интерфейс без необходимости “лезть в железо” и оркестратор.

Система реализует сценарий:

1) **Разработчик** создаёт заявку на развёртывание (описание будущего контейнерного образа + ресурсы).
2) **Оператор** проверяет заявку, при необходимости корректирует параметры, затем запускает **имитацию** сборки образа.
3) После успешной “сборки” в системе появляется **образ**.
4) Оператор создаёт **развёртывания** (несколько экземпляров/портов) и управляет ими (start/stop/restart/delete).
5) Система генерирует **логи** и **метрики CPU/RAM** для развёртываний и отображает их в UI (реальные графики + реалтайм лог‑стрим).
6) **Администратор** управляет пользователями (создание, блокировка) и смотрит полный аудит.

Реальные Docker/Kubernetes операции НЕ выполняются — всё имитируется фоновой логикой.

***

## 2. Стек и ограничения

### 2.1. Технологии

- Backend: **Python 3.11+**, Flask.
- Frontend: **HTML + CSS**, допускается “немного JS” для графиков и SSE.
- База данных: **SQLite**.
- Шаблонизатор: Jinja2 (в составе Flask).
- Авторизация/сессии: Flask‑Login (рекомендуется, минимально).
- Графики: Chart.js (подключение через CDN).[^2]
- Реалтайм логи: SSE (`EventSource` в браузере).[^3]


### 2.2. Обязательные требования

- При запуске система **создаёт БД**, если её нет (файл + таблицы).[^1]
- При первом запуске создаётся администратор: **root:root**.
- Должен быть `requirements.txt`.
- Имитация сборки/деплоя/логов/метрик — обязательна.
- Графики метрик должны реально строиться в браузере (не ASCII), логи должны выводиться в реальном времени.

***

## 3. Роли и права доступа (RBAC)

### 3.1. Роли

- **admin**
- **operator**
- **developer**


### 3.2. Политика доступа

- **Создание пользователей и блокировка**: только `admin`.
- **Просмотр заявок**:
    - `operator/admin`: все заявки.
    - `developer`: только заявки где:
        - он `created_by`, или
        - он `owner_id`, или
        - его логин присутствует в `collaborators` (строка со списком логинов).
- **Сборка образа**: только `operator/admin`.
- **Развёртывания**:
    - `operator/admin`: создаёт/управляет любыми.
    - `developer`:
        - видит развёртывания, связанные с доступными ему заявками/образами;
        - может start/stop/restart только если он **owner** заявки/образа **и** развёртывание НЕ остановлено оператором (`stopped_by_operator=1` запрещает старт разработчиком).

***

## 4. Функциональные требования (Use Cases)

### 4.1. Авторизация

- Страница `/login` (username/password).
- Заблокированный пользователь (`is_active=0`) не может войти.
- После успешного входа — редирект на `/dashboard`.


### 4.2. Заявки (image_requests)

Разработчик создаёт заявку, указывая:

- `image_name` — имя образа (будущий тег/маркер).
- `repo_url` — URL репозитория.
- `repo_branch` — ветка (по умолчанию main).
- `update_mode` — continuous/static.
- `target_commit` — обязателен, если static.
- `base_image` — базовый образ (FROM).
- `run_commands` — список команд RUN (упрощение: многострочное поле, по строке на команду).
- `entrypoint` — строка стартовой команды.
- `ram_mb`, `vcpu` — требуемые ресурсы.
- `version_tag` — “версия/метка” (строка, задаёт разработчик; может быть произвольной).
- `collaborators` — список логинов (через запятую) с подсказками из существующих пользователей.
- `owner_id` — главный ответственный (логин выбирается из списка существующих пользователей, только role=developer).

Статусы заявки:

- `draft` (черновик)
- `submitted` (отправлено оператору)
- `in_review` (на рассмотрении)
- `approved` (одобрено к сборке)
- `rejected` (отклонено)

Оператор может:

- переводить статус,
- корректировать параметры,
- запускать сборку.


### 4.3. Сборки (builds) — имитация

Оператор запускает сборку по заявке:

- создаётся build со статусом `queued` → `building` → `success/failed`.
- генерируется лог сборки (пополняемый во времени).
- при success создаётся образ `images`.


### 4.4. Образы (images)

Образ — результат успешной сборки:

- содержит `name`, `version` (метка из заявки), `image_tag = name:version`.
- из образа можно создавать deployments.


### 4.5. Развёртывания (deployments) — имитация

Оператор создаёт развёртывание:

- name (человекочитаемое)
- environment (dev/staging/prod)
- replicas
- ports (одна строка формата `8000:8000,8001:8001`)
- статус: deploying → running (или иногда failed)
- флаги:
    - `stopped_by_operator` (если оператор остановил — разработчик не может стартануть)
    - `needs_restart` (если изменился base_image — требует рестарта)

Управление:

- start/stop/restart/delete


### 4.6. Имитация “нового коммита” (универсальный endpoint)

Нужен endpoint для внешних интеграций (в будущем GitHub Actions/GitLab CI):

- `POST /api/hooks/commit`
Вход: `{ "repo_url": "...", "branch": "...", "commit": "sha" }`
- Поведение:
    - найти заявки с `update_mode=continuous`, совпадающие по `repo_url` и `repo_branch`
    - для связанных deployments выполнить “автоматический restart”
    - записать аудит (и желательно лог‑событие в логах deployment)

Для UI должна быть кнопка “Симулировать новый коммит” на странице заявки или образа, которая вызывает этот endpoint.

### 4.7. Логи и метрики

- Для каждого `running` deployment система генерирует:
    - лог‑строки (1–3 строки/сек)
    - метрики CPU/RAM (1 точка/сек)
- Логи должны быть доступны:
    - “последние N строк” (например 200)
    - “реалтайм стрим” через SSE (один общий поток на deployment для всех клиентов).[^3]
- Метрики должны отображаться графиками Chart.js:
    - CPU % (0..100)
    - RAM % (0..100) или RAM MB (рекомендуется % для простоты)
- Данные метрик можно хранить в памяти (кольцевой буфер последних 10–15 минут).


### 4.8. Админка

Только admin:

- создание пользователя (username, password, role)
- блокировка/разблокировка пользователя
- просмотр audit_log с фильтрами (по пользователю, по action, по тексту)
- root нельзя удалить и нельзя заблокировать (фиксировать как правило).

***

## 5. Нефункциональные требования

### 5.1. UI/UX и тема

- Основная тема: тёмная, фон близкий к чёрному, акценты красные, текст светлый/белый.
- Таблицы с “зеброй” или подсветкой строк.
- Статусы отображать бейджами:
    - success/running — зелёный или спокойный “лайм”
    - failed/rejected — красный
    - building/deploying/in_review — жёлтый/оранжевый
    - stopped — серый


### 5.2. Безопасность (минимум)

- Пароли хранятся только в виде хеша.
- Все SQL запросы параметризованные.
- Проверка прав на каждом маршруте.


### 5.3. Производительность (MVP)

- Метрики и логи ограничиваются по объёму:
    - логи: хранить последние 1000 строк на deployment (кольцевой буфер)
    - метрики: хранить последние 900 точек (15 минут при 1/sec)
- SSE соединения должны корректно закрываться.

***

## 6. База данных (SQLite) — схема

### 6.1. Файл и создание

- Файл БД хранится в `instance/samosval.sqlite3`.
- При старте приложения:
    - если файла нет → создать и выполнить SQL схему (например `schema.sql` + `executescript`).[^1]
    - если root отсутствует → создать root:root.


### 6.2. Таблицы (минимально достаточные)

**users**

- id INTEGER PK AUTOINCREMENT
- username TEXT UNIQUE NOT NULL
- password_hash TEXT NOT NULL
- role TEXT NOT NULL
- is_active INTEGER NOT NULL (0/1)
- created_at TEXT NOT NULL

**image_requests**

- id INTEGER PK
- image_name TEXT NOT NULL
- repo_url TEXT NOT NULL
- repo_branch TEXT NOT NULL
- update_mode TEXT NOT NULL
- target_commit TEXT NULL
- base_image TEXT NOT NULL
- run_commands TEXT NULL
- entrypoint TEXT NULL
- dockerfile_content TEXT NULL
- ram_mb INTEGER NOT NULL
- vcpu REAL NOT NULL
- version_tag TEXT NOT NULL
- owner_id INTEGER NOT NULL FK→users.id
- status TEXT NOT NULL
- collaborators TEXT NULL
- created_by INTEGER NOT NULL FK→users.id
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

**images**

- id INTEGER PK
- request_id INTEGER NOT NULL FK→image_requests.id
- name TEXT NOT NULL
- version TEXT NOT NULL
- image_tag TEXT NOT NULL
- created_at TEXT NOT NULL

**builds**

- id INTEGER PK
- request_id INTEGER NOT NULL FK→image_requests.id
- image_id INTEGER NULL FK→images.id
- status TEXT NOT NULL
- build_log TEXT NULL
- error_message TEXT NULL
- built_by INTEGER NOT NULL FK→users.id
- created_at TEXT NOT NULL

**deployments**

- id INTEGER PK
- image_id INTEGER NOT NULL FK→images.id
- name TEXT NOT NULL
- environment TEXT NOT NULL
- status TEXT NOT NULL
- replicas INTEGER NOT NULL
- ports TEXT NULL
- stopped_by_operator INTEGER NOT NULL (0/1)
- needs_restart INTEGER NOT NULL (0/1)
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

**alerts**

- id INTEGER PK
- alert_type TEXT NOT NULL
- target_id INTEGER NOT NULL
- message TEXT NOT NULL
- resolved INTEGER NOT NULL (0/1)
- created_at TEXT NOT NULL

**audit_log**

- id INTEGER PK
- user_id INTEGER NULL FK→users.id
- action TEXT NOT NULL
- target_id INTEGER NULL
- details TEXT NULL
- created_at TEXT NOT NULL

***

## 7. Архитектура backend

### 7.1. Файловая структура проекта (обязательная)

```
samosval/
  app.py
  requirements.txt
  schema.sql
  instance/
    samosval.sqlite3        (автосоздание)
  samosval/
    __init__.py
    db.py                   (connect/get_db/init_db)
    auth.py                 (Flask-Login user_loader, login/logout)
    access.py               (role_required, helpers can_view_request etc.)
    simulator/
      engine.py             (фоновые циклы)
      state.py              (in-memory buffers: logs+metrics)
    routes/
      auth_routes.py
      dashboard_routes.py
      request_routes.py
      build_routes.py
      image_routes.py
      deployment_routes.py
      admin_routes.py
      api_routes.py
    templates/
      ... (html)
    static/
      css/theme.css
      js/metrics.js
      js/logs_sse.js
```


### 7.2. Инициализация БД

- `init_db_if_needed()`:
    - создаёт файл SQLite и выполняет `schema.sql`, если надо.[^1]
    - создаёт root:root если нет
- Вызывается при старте `app.py` до `app.run()`.

***

## 8. Симуляция (фоновые процессы)

### 8.1. Общая идея

Один фоновый поток “SimulationEngine” (daemon thread) выполняет:

- обработку активных build (queued/building)
- обработку deploying deployments
- генерацию runtime логов и метрик для running deployments


### 8.2. Хранение логов/метрик

- Логи и метрики хранятся **в памяти** в структурах вида:
    - `deployment_logs[deployment_id] = deque(maxlen=1000)`
    - `deployment_metrics[deployment_id] = deque(maxlen=900)` (каждый элемент: ts,cpu,ram)
- Доступ синхронизировать через Lock.


### 8.3. Алгоритм имитации build

При запуске build:

- builds.status=queued
- через 1–2 сек → building
- каждые 0.5–1.5 сек добавлять строку в build_log
- итог:
    - success: создать image и связать builds.image_id
    - failed: error_message + финальный лог
- писать audit_log: build_start/build_finish


### 8.4. Алгоритм имитации deployment

При создании deployment:

- status=deploying
- через 3–8 сек → running (или иногда failed)
- если failed — добавить alert + аудит


### 8.5. Логи runtime

Для running deployment:

- каждую секунду добавлять 1–3 строки:
    - INFO/WARN/ERROR (распределение: 80/15/5)
    - включать имя deployment и образ/tag
- Эти логи видны всем открывшим страницу (общий поток).


### 8.6. Метрики

Для running deployment:

- каждую секунду:
    - cpu = random walk (плавно), 0..100
    - ram = random walk, 0..100
- API возвращает массивы для графика.

***

## 9. Маршруты (страницы) и поведение

### 9.1. Auth

- `GET /login` — форма
- `POST /login` — логин
- `POST /logout` — выход


### 9.2. Dashboard

- `GET /dashboard`
    - карточки: заявки по статусам, deployments по статусам, последние audit события


### 9.3. Requests

- `GET /requests` — список + фильтры
- `GET /requests/new` — создание (developer)
- `POST /requests/new` — сохранить draft
- `POST /requests/<id>/submit` — перевести в submitted (developer)
- `GET /requests/<id>` — карточка
- `POST /requests/<id>/edit` — редактирование (developer в своих пределах, operator/admin полностью)
- `POST /requests/<id>/status` — смена статуса (operator/admin)
- `POST /requests/<id>/build` — запуск сборки (operator/admin)


### 9.4. Builds

- `GET /builds`
- `GET /builds/<id>` — просмотр + автообновление логов
- `GET /api/builds/<id>/log` — JSON для polling


### 9.5. Images

- `GET /images`
- `GET /images/<id>` — детали + deployments списка
- (опционально) `POST /images/<id>/create_deployment`


### 9.6. Deployments

- `GET /deployments` — список
- `GET /deployments/<id>` — детали (логи+метрики)
- `POST /deployments/<id>/start`
- `POST /deployments/<id>/stop`
- `POST /deployments/<id>/restart`
- `POST /deployments/<id>/delete`

Правила start/stop:

- operator/admin всегда может
- developer только если owner и не stopped_by_operator


### 9.7. Admin

- `GET /admin/users`
- `POST /admin/users/create`
- `POST /admin/users/<id>/block`
- `POST /admin/users/<id>/unblock`
- `GET /admin/audit`


### 9.8. API для подсказок логинов (autocomplete)

- `GET /api/users/search?q=<prefix>`
    - отдаёт JSON массив логинов
    - используется в форме заявки для:
        - owner
        - collaborators
- В UI использовать `<datalist>` (нативный автокомплит).[^4]


### 9.9. API для “нового коммита”

- `POST /api/hooks/commit`
    - body: repo_url, branch, commit
    - effect:
        - для continuous заявок/образов: пометить needs_restart или выполнить авто‑restart deployments
        - аудит: commit_hook_received, deployments_restarted


### 9.10. SSE поток логов

- `GET /api/deployments/<id>/logs/stream` (SSE)
    - отдаёт текст/event-stream
    - каждые N мс пушит новые строки из буфера
    - клиент: EventSource на странице deployment_detail.[^3]


### 9.11. Метрики JSON

- `GET /api/deployments/<id>/metrics`
    - отдаёт labels/cpu/ram для Chart.js

***

## 10. UI формы (минимум)

### 10.1. Создание/редактирование заявки

- Поля (как в требованиях) +:
    - owner — input с datalist (подсказки)
    - collaborators — текстовое поле со списком логинов через запятую + подсказки (реализовать “добавление логина” кнопкой: выбрал из datalist → добавить в строку)
- Валидации:
    - static → commit обязателен
    - ram_mb/vcpu > 0


### 10.2. Deployment detail

- Блок метрик: 2 line chart (CPU/RAM) с обновлением каждые 2–3 сек.
- Блок логов:
    - кнопки: Start/Stop/Restart (по правам)
    - окно логов monospace
    - toggle “Realtime” (подключает SSE)


### 10.3. Admin users

- Таблица пользователей (username/role/is_active)
- Создание пользователя
- Block/Unblock (root нельзя блокировать)

***

## 11. requirements.txt (обязательно)

Минимально:

- Flask
- Flask-Login
- Werkzeug

(Chart.js через CDN, в requirements не нужен.)[^2]

***

## 12. Критерии приёмки

1) Запуск `python app.py`:

- создаёт `instance/samosval.sqlite3`, если нет.[^1]
- создаёт `root:root` admin, если нет.

2) root может:

- создать developer и operator
- блокировать/разблокировать пользователей
- смотреть аудит

3) developer может:

- создать draft заявку
- указать owner и collaborators по логинам с подсказками
- submit заявку

4) operator может:

- просмотреть заявку, изменить параметры, approved
- запустить build → видеть живые логи → получить image
- создать deployment → увидеть running
- открыть deployment detail → увидеть realtime логи (SSE) и метрики (Chart.js)

5) Кнопка “Simulate commit” (или POST endpoint) приводит к автоперезапуску (или пометке и рестарту) continuous‑deployments и фиксируется в аудите.

***

## 13. Замечания для Cursor (как писать код)

- Начать с каркаса Flask + шаблоны + авторизация.
- Затем реализовать `schema.sql` и `init_db_if_needed()` (создание таблиц + root).[^1]
- Затем CRUD заявок и RBAC.
- Затем симулятор builds/deployments + in-memory buffers.
- Затем SSE endpoint и Chart.js графики.[^2][^3]
- Затем admin users + audit.

Если нужно, следующим сообщением могу выдать:

- готовый `schema.sql` под эту схему,
- макеты HTML страниц (Jinja2) и CSS тему (чёрный/красный/белый),
- “контракт” JSON для metrics и SSE форматы, чтобы Cursor агент не гадал.
<span style="display:none">[^10][^11][^12][^13][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://flask.palletsprojects.com/en/stable/patterns/sqlite3/

[^2]: https://masteringjs.io/tutorials/chartjs/cdn

[^3]: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events

[^4]: https://www.sitepoint.com/html5-datalist-autocomplete/

[^5]: https://stackoverflow.com/questions/60875811/how-to-automatically-create-database-tables-and-schema-with-flask-and-sqalchemy

[^6]: https://flask.palletsprojects.com/en/stable/tutorial/database/

[^7]: https://devcamp.com/trails/python-api-development-with-flask/campsites/hello-flask/guides/creating-sqlite-database-flask-sqlalchemy

[^8]: https://www.digitalocean.com/community/tutorials/how-to-use-an-sqlite-database-in-a-flask-application

[^9]: https://www.geeksforgeeks.org/python/python-sqlite-create-table/

[^10]: https://www.youtube.com/watch?v=_U_hJZ9uA2g

[^11]: https://flask-sqlalchemy.readthedocs.io/en/stable/quickstart/

[^12]: https://labex.io/tutorials/python-flask-sqlite-database-setup-136336

[^13]: https://github.com/miguelgrinberg/Flask-Migrate/issues/153

