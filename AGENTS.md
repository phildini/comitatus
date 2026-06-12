# comitatus — AGENTS.md

## Architecture

POSSE personal site platform. Two deploy targets from one repo:
- **`admin.phildini.net`** — Django app (Fly.io). Editing/posting interface.
- **`phildini.net`** — Static HTML on GitHub Pages (`gh-pages` branch). No running Python.

## Key commands

```bash
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

No test, lint, or typecheck runners configured yet. `/admin/` is the sole Django URL.

## Structure

| Path | Role |
|---|---|
| `posts/` | Django app: models, admin, syndication, management commands |
| `posts/management/commands/build_site.py` | Generates `site/` from templates + DB, pushes to `gh-pages` |
| `posts/management/commands/publish_scheduled.py` | Publishes scheduled posts, triggers build |
| `posts/management/commands/syndicate.py` | Resyndicates published posts to Bluesky/Mastodon |
| `posts/syndication/bluesky.py` | atproto client |
| `posts/syndication/mastodon.py` | Mastodon.py client |
| `posts/deploy.py` | GitPython push to `gh-pages` using `GITHUB_DEPLOY_KEY` |
| `templates/site/` | Central template dir — Django renders these for the static site |
| `static/` | Assets copied into static site build |
| `site/` | Static site build output (gitignored, pushed to `gh-pages`) |
| `data/` | SQLite database location (gitignored, Fly Volume on prod) |

## Data model

Single `Post` model: `uuid` (PK), `post_type` (long/micro), `title`, `body` (Markdown), `image`, `published_at`, `is_published`, `syndication_urls` (JSON).

## Save flow (in `posts/admin.py`)

When a post is saved with `is_published=True`:
1. Syndicate to Bluesky + Mastodon
2. Run `build_site` (generate HTML + push to `gh-pages`)
3. GitHub Pages serves `phildini.net`

## Environment (all via env vars)

`DJANGO_SECRET_KEY`, `SITE_DOMAIN`, `BLUESKY_USERNAME`, `BLUESKY_PASSWORD`, `MASTODON_ACCESS_TOKEN`, `MASTODON_BASE_URL`, `WEBMENTION_IO_TOKEN`, `GITHUB_DEPLOY_KEY`, `GITHUB_REPO_URL`. See `.env.example`.

## Deploy (Fly.io + GitHub Pages)

| App | Hosting | Method |
|---|---|---|
| **Django admin** (`admin.phildini.net`) | Fly.io | `Dockerfile` uses `uv`, entrypoint runs migrate + gunicorn |
| **Static site** (`phildini.net`) | GitHub Pages | `posts/deploy.py` pushes `site/` to `gh-pages` via `GITHUB_DEPLOY_KEY` |

Fly secrets (`fly secrets set ...`): all env vars in `.env.example` plus `DJANGO_ALLOWED_HOSTS`.
Fly Volume at `/data` for SQLite persistence.

GitHub Action `.github/workflows/fly-deploy.yml` auto-deploys on push to `main`.

`.github/workflows/fly-deploy.yml` cannot be pushed via HTTPS token (GitHub blocks OAuth workflow edits). Must be pushed from a machine with SSH or PAT with `workflow` scope.

Static site: Django pushes `site/` to `gh-pages` → GitHub Action in `.github/workflows/pages.yml` deploys to Pages.

## Gotchas

- SQLite path is `BASE_DIR / "data" / "db.sqlite3"` locally, but `/data/db.sqlite3` on Fly (set `DATABASE_PATH` env var). The `data/` dir must exist locally; on Fly the volume at `/data` provides it.
- Django app imports (`posts.admin`) trigger syndication + build on save. Tests (when added) should mock `_build_site` and syndication.
- `atproto` and `Mastodon.py` are runtime deps; no syndication happens without credentials.
