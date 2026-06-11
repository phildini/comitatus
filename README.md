# comitatus

POSSE personal site platform — **P**ublish (on your) **O**wn **S**ite, **S**yndicate **E**lsewhere.

- **Editing**: Django admin app (deployed to `admin.phildini.net`)
- **Public site**: Static HTML on GitHub Pages (`phildini.net`)
- **Syndication**: Automatically posts to Bluesky and Mastodon on publish

## Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│ admin.phildini.net   │     │ phildini.net          │
│ Django (Fly.io)      │     │ GitHub Pages (static) │
│                      │     │                      │
│ Write/edit posts ────┼────>│ Homepage + blog feed │
│ Syndicate to socials │     │ Individual posts     │
│ Build static site ───┼────>│ Archive + RSS        │
│ Push to gh-pages     │     │ Webmentions          │
└──────────────────────┘     └──────────────────────┘
```

## Setup

### Prerequisites

- Python 3.12+
- GitHub account with Pages enabled on the repo
- Bluesky account
- Mastodon account
- (Optional) Fly.io account for hosting the admin app

### Local Development

```bash
# Clone the repo
git clone git@github.com:phildini/comitatus.git
cd comitatus

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run migrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Start the dev server
python manage.py runserver
```

Visit `http://localhost:8000/admin/` and log in.

### Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Django secret key |
| `DJANGO_DEBUG` | No | Set to `True` for local dev |
| `DJANGO_ALLOWED_HOSTS` | No | Comma-separated hostnames |
| `SITE_DOMAIN` | Yes | Your domain (e.g., `phildini.net`) |
| `BLUESKY_USERNAME` | For syndication | Bluesky handle |
| `BLUESKY_PASSWORD` | For syndication | Bluesky app password |
| `MASTODON_ACCESS_TOKEN` | For syndication | Mastodon API token |
| `MASTODON_BASE_URL` | For syndication | Mastodon instance URL |
| `WEBMENTION_IO_TOKEN` | For webmentions | webmention.io API token |
| `GITHUB_DEPLOY_KEY` | For deploy | SSH key with push access to gh-pages |
| `GITHUB_REPO_URL` | For deploy | Git SSH URL of the repo |

### Deploying the Admin App (Fly.io)

```bash
# Install flyctl if you haven't already
curl -fsSL https://fly.io/install.sh | sh

# Launch the app
fly launch

# Set secrets
fly secrets set \
  DJANGO_SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())") \
  SITE_DOMAIN=phildini.net \
  BLUESKY_USERNAME=... \
  BLUESKY_PASSWORD=... \
  MASTODON_ACCESS_TOKEN=... \
  MASTODON_BASE_URL=... \
  WEBMENTION_IO_TOKEN=... \
  GITHUB_DEPLOY_KEY="$(cat ~/.ssh/deploy_key)"

# Attach a volume for SQLite persistence
fly volumes create data --size 1
fly deploy
```

### Setting Up the GitHub Deploy Key

The Django app needs to push to the `gh-pages` branch of the repo.

1. Generate a deploy key:
   ```bash
   ssh-keygen -t ed25519 -C "comitatus-deploy" -f ~/.ssh/comitatus_deploy
   ```

2. Add the **public key** as a deploy key in your GitHub repo settings:
   - Settings → Deploy keys → Add deploy key
   - Allow write access

3. Set the **private key** as a Fly secret (see above)

### Setting Up Social Syndication

#### Bluesky

1. Go to Settings → App Passwords in Bluesky
2. Create an app password (e.g., "comitatus")
3. Set `BLUESKY_USERNAME` and `BLUESKY_PASSWORD` as Fly secrets

#### Mastodon

1. Go to Settings → Development in Mastodon
2. Create a new application with `write:statuses` and `write:media` scopes
3. Copy the access token
4. Set `MASTODON_ACCESS_TOKEN` and `MASTODON_BASE_URL` as Fly secrets

### Setting Up Webmentions

1. Sign up at [webmention.io](https://webmention.io)
2. Add your domain
3. Copy the API token
4. Set `WEBMENTION_IO_TOKEN` as a Fly secret

The `<link rel="webmention">` tags are already in the site templates.

## Usage

### Creating a Post

1. Go to `admin.phildini.net` and log in
2. Click "Posts" → "Add Post"
3. Choose **Long-form** or **Micro-post**
4. For long-form: add a title and body (Markdown)
5. For micro-posts: write short text, optionally attach an image
6. Check **Is published** to publish immediately
7. Or set **Published at** to a future date for scheduled publishing

### Publishing Flow

When you save a post with **Is published** checked:

1. Post is saved to the database
2. Syndicated to Bluesky and Mastodon (with image attachment for micro-posts)
3. Static site is generated to `site/`
4. `site/` is pushed to the `gh-pages` branch
5. GitHub Pages serves the updated site at `phildini.net`

### Scheduled Posts

Set a future `published_at` date and leave **Is published** unchecked.
The `publish_scheduled` management command (run via Fly cron) will publish
it automatically when the time comes.

### Admin Actions

In the Posts list view, you can:
- **Resyndicate selected posts** — re-post to Bluesky and Mastodon
- **Rebuild and deploy the static site** — manually trigger a rebuild

## Customizing the Static Site

- **Templates**: `templates/site/` — HTML templates rendered by Django
- **CSS**: `static/css/site.css` — overrides for Pico.css
- **Homepage bio**: Edit `templates/site/home.html`
- **Now page**: Edit `templates/site/now.html`

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.x |
| Database | SQLite (Fly Volume) |
| Admin host | Fly.io |
| Static host | GitHub Pages |
| CSS | Pico.css |
| Bluesky | atproto |
| Mastodon | Mastodon.py |
| Markdown | Python-Markdown |

## License

BSD 3-Clause. See [LICENSE](LICENSE).
