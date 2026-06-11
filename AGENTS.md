# LinkGnome

Monorepo with two Python packages — a CLI library (`linkgnome`) and a Django web app (`linkgnome-web`).

## Two projects, two uv envs

- **Library:** root dir — `uv sync`, `uv run pytest tests/`
- **Web app:** `web/` dir — `cd web && uv sync`, `cd web && DJANGO_SETTINGS_MODULE=config.settings pytest tests/`
- Web depends on library via `[tool.uv.sources] linkgnome = { path = ".." }`
- Each has its own `uv.lock` — commit both

## Commands

### Library (root)
```
uv sync                      # install deps
uv run pytest tests/         # run library tests
uv run ruff check src/       # lint
```

### Web app (`web/`)
```
cd web && uv sync                       # install deps (includes library from ..)
cd web && uv run python manage.py migrate
cd web && uv run python manage.py createcachetable
cd web && DJANGO_SETTINGS_MODULE=config.settings pytest tests/
cd web && uv run python manage.py runserver
cd web && npm run build                 # rebuild Tailwind CSS after template changes
```

### Makefile shortcuts
```
make web-install    # uv sync + npm install + build-css
make web-dev        # runserver
make web-css        # tailwind --watch
make web-build-css  # tailwind --minify
```

## Architecture

- **Library** (`src/linkgnome/`): Mastodon/Bluesky API fetchers, engagement scoring (post×1.0 + boost×0.5 + like×0.25 × time decay), URL normalization, title extraction via BeautifulSoup, SQLite metadata cache. CLI entrypoint via `linkgnome` command.
- **Web app** (`web/`): Django 5.1 app with `accounts`, `feeds`, `billing`, `links` apps. Magic-link auth via django-stagedoor (no passwords). HTMX-driven dashboard. Tailwind CSS + daisyUI with custom "gnome" theme.
- **ScoredLink** (24h, per-user, bulk-replaced on refresh) vs **PersistentLink** (historical, cross-user, via Identity→Follow→User JOIN).
- **Background tasks:** django-q2 with ORM broker. `fetch_user_feeds` fetches + scores + persists. Scheduled every 5 min via `fetch_all_feeds` management command.

## Key quirks

- **Web tests need env vars:** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DATA_DIR`, `LINKGNOME_CACHE_PATH` (see CI workflow).
- **`web/requirements.txt` is stale** — ignore it, use `pyproject.toml` and `uv.lock`.
- **Docker build context is repo root** (not `web/`), `fly.toml` sets `dockerfile = 'web/Dockerfile'`.
- **Cache backend is DatabaseCache** — `createcachetable` runs in entrypoint.
- **Data migrations exist:** `accounts.0003_set_site_domain` (sets `linkgno.me`), `billing.0003_seed_prices` (seeds Gnome $5/mo + $50/yr).
- **Stripe:** driven by `Price` model (manage via admin), requires `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` env vars.
- **Postmark email:** auto-detected from `POSTMARK_TOKEN` env var.
- **gnome daisyUI theme** defined in `web/tailwind.config.js` — green/earthy.
- **Entrypoint:** `web/docker-entrypoint.sh` runs migrate → createcachetable → qcluster → gunicorn.
- **CI:** library tests on 3.10–3.13, web tests on 3.12. Both run on every push/PR.
- **Deploy:** Fly.io from `main` on `web/**` changes. PyPI publish from `main` on `src/**` changes.
