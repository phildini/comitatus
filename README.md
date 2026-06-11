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
- A GitHub account (for repo and Pages)
- A Bluesky account (for syndication)
- A Mastodon account (for syndication)
- A [Fly.io](https://fly.io) account (for hosting the admin app)
- A domain you control (e.g., `phildini.net`)

### Local Development

```bash
uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://localhost:8000/admin/` and log in.

---

## Deployment Guide

### Step 1: GitHub Repo + Pages

1. Push the repo to GitHub
2. Go to repo Settings → Pages → Source: **Deploy from branch**
3. Branch: `gh-pages`, folder: `/ (root)`
4. The `.github/workflows/pages.yml` will deploy on every push to `gh-pages`
5. Later, set your custom domain in the Pages settings tab (after DNS below)

### Step 2: DNS Setup

These are your two domains — set them up at your DNS provider:

| Record | Type | Value |
|---|---|---|
| `phildini.net` | CNAME | `<your-username>.github.io` |
| `admin.phildini.net` | CNAME | `comitatus.fly.dev` (get this after `fly launch` below) |

GitHub Pages will use the `CNAME` file already in the `gh-pages` branch.

### Step 3: Fly.io App Setup

```bash
# Install flyctl
curl -fsSL https://fly.io/install.sh | sh

# Log in
fly auth login

# Launch the app (use the existing fly.toml)
fly launch --no-deploy

# Attach a persistent volume for SQLite
fly volumes create data --region sjc --size 1

# Set all secrets (see Step 4-7 for where values come from)
fly secrets set \
  DJANGO_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))") \
  SITE_DOMAIN=phildini.net \
  DJANGO_ALLOWED_HOSTS=admin.phildini.net,comitatus.fly.dev \
  BLUESKY_USERNAME=your-handle.bsky.social \
  BLUESKY_PASSWORD='xxx' \
  MASTODON_ACCESS_TOKEN='xxx' \
  MASTODON_BASE_URL=https://mastodon.social \
  WEBMENTION_IO_TOKEN='xxx' \
  GITHUB_DEPLOY_KEY='xxx' \
  GITHUB_REPO_URL=git@github.com:phildini/comitatus.git

# Deploy
fly deploy
```

After deploy, note the Fly app hostname:
```bash
fly status
# Look for "Hostname: comitatus.fly.dev"
```

### Step 4: GitHub Deploy Key

The Django admin app needs permission to push the generated static site to the `gh-pages` branch.

```bash
# Generate a deploy key (on your local machine)
ssh-keygen -t ed25519 -C "comitatus-deploy" -f ~/.ssh/comitatus_deploy
```

This creates two files:
- `~/.ssh/comitatus_deploy` — **private key** (put this in Fly secrets as `GITHUB_DEPLOY_KEY`)
- `~/.ssh/comitatus_deploy.pub` — **public key** (goes to GitHub)

Add the **public key** to GitHub:
1. Go to https://github.com/phildini/comitatus/settings/keys
2. Click **Add deploy key**
3. Title: `comitatus-deploy`
4. Key: paste the contents of `~/.ssh/comitatus_deploy.pub`
5. Check **Allow write access** (required so Django can push to `gh-pages`)

Set the **private key** as a Fly secret (one line, with newlines):
```bash
fly secrets set GITHUB_DEPLOY_KEY="$(cat ~/.ssh/comitatus_deploy)"
```

### Step 5: Bluesky Syndication

1. Log in to Bluesky in a browser
2. Go to **Settings** → **App Passwords**
3. Click **Add App Password**
4. Name it `comitatus`
5. Copy the generated password (looks like `xxxx-xxxx-xxxx-xxxx`)
6. Set as Fly secrets:
   ```bash
   fly secrets set BLUESKY_USERNAME=your-handle.bsky.social
   fly secrets set BLUESKY_PASSWORD='xxxx-xxxx-xxxx-xxxx'
   ```

Note: Use your full handle (e.g., `phildini.bsky.social`), not just `@phildini`.

### Step 6: Mastodon Syndication

1. Log in to your Mastodon instance (e.g., `mastodon.social`)
2. Go to **Preferences** → **Development** (URL: `https://mastodon.social/settings/applications`)
3. Click **New Application**
4. Application name: `comitatus`
5. Scopes: enable **`write:statuses`** and **`write:media`** only
6. Click **Submit**
7. Copy the **Your access token** string (long random string)
8. Set as Fly secrets:
   ```bash
   fly secrets set MASTODON_ACCESS_TOKEN='your-access-token'
   fly secrets set MASTODON_BASE_URL=https://mastodon.social
   ```

### Step 7: Webmentions (Optional)

1. Go to https://webmention.io and sign in with IndieAuth (your domain)
2. Add your domain (`phildini.net`)
3. Copy the API token from the settings page
4. Set as Fly secret:
   ```bash
   fly secrets set WEBMENTION_IO_TOKEN='your-token'
   ```

The `<link rel="webmention">` tags are already in the site templates. Webmentions are fetched at build time and embedded in post pages.

### Step 8: Deploy

```bash
# Push the workflow file from your machine (needs workflow scope)
git add .github/workflows/fly-deploy.yml
git commit -m "Add Fly.io deploy workflow"
git push origin main

# Or deploy manually
fly deploy

# Verify
fly logs
```

### Step 9: Verify It Works

1. Visit `https://admin.phildini.net` — you should see the Django admin login
2. Log in with the superuser you created
3. Create a test post with **Is published** checked
4. Check `https://phildini.net` — the post should appear
5. Check Bluesky and Mastodon — the post should be syndicated

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
