import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import markdown
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from posts.models import Post

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate static site and deploy to GitHub Pages"

    def handle(self, *args, **options):
        site_dir = Path(settings.BASE_DIR) / "site"
        if site_dir.exists():
            shutil.rmtree(site_dir)
        site_dir.mkdir(parents=True, exist_ok=True)

        posts_dir = site_dir / "posts"
        posts_dir.mkdir(parents=True, exist_ok=True)

        posts = (
            Post.objects.filter(is_published=True, published_at__isnull=False)
            .filter(published_at__lte=timezone.now())
            .order_by("-published_at")
        )

        rendered_posts = []
        for post in posts:
            rendered = self._render_post(post)
            rendered_posts.append(rendered)

            post_dir = posts_dir / str(post.uuid)
            post_dir.mkdir(parents=True, exist_ok=True)

            html = render_to_string(
                "site/post.html",
                {
                    "post": rendered,
                    "site_domain": settings.SITE_DOMAIN,
                    "now": timezone.now(),
                },
            )
            (post_dir / "index.html").write_text(html)

        html = render_to_string(
            "site/home.html",
            {
                "posts": rendered_posts,
                "site_domain": settings.SITE_DOMAIN,
                "now": timezone.now(),
            },
        )
        (site_dir / "index.html").write_text(html)

        html = render_to_string(
            "site/archive.html",
            {
                "posts": rendered_posts,
                "site_domain": settings.SITE_DOMAIN,
                "now": timezone.now(),
            },
        )
        (site_dir / "archive" / "index.html").parent.mkdir(parents=True, exist_ok=True)
        (site_dir / "archive" / "index.html").write_text(html)

        html = render_to_string(
            "site/now.html",
            {
                "site_domain": settings.SITE_DOMAIN,
                "now": timezone.now(),
            },
        )
        (site_dir / "now" / "index.html").parent.mkdir(parents=True, exist_ok=True)
        (site_dir / "now" / "index.html").write_text(html)

        feed_xml = render_to_string(
            "site/feed.xml",
            {
                "posts": rendered_posts[:20],
                "site_domain": settings.SITE_DOMAIN,
                "now": timezone.now(),
            },
        )
        (site_dir / "feed.xml").write_text(feed_xml)

        with open(site_dir / "CNAME", "w") as f:
            f.write(settings.SITE_DOMAIN + "\n")

        static_src = Path(settings.BASE_DIR) / "static"
        static_dst = site_dir / "static"
        if static_src.exists():
            shutil.copytree(static_src, static_dst, symlinks=True)

        media_src = Path(settings.MEDIA_ROOT)
        media_dst = site_dir / "media"
        if media_src.exists():
            shutil.copytree(media_src, media_dst, symlinks=True)

        self._fetch_webmentions(site_dir, rendered_posts)

        logger.info("Static site generated at %s", site_dir)
        self.stdout.write(self.style.SUCCESS(f"Static site generated at {site_dir}"))

        from posts.deploy import deploy_to_gh_pages

        success = deploy_to_gh_pages(str(site_dir))
        if success:
            self.stdout.write(self.style.SUCCESS("Deployed to gh-pages"))
        else:
            self.stdout.write(self.style.WARNING("Deploy skipped or failed"))

    def _render_post(self, post):
        body_html = markdown.markdown(
            post.body,
            extensions=["fenced_code", "codehilite", "smarty", "extra"],
        )

        webmentions = []

        return {
            "uuid": str(post.uuid),
            "post_type": post.post_type,
            "title": post.title,
            "body_html": body_html,
            "body": post.body,
            "image_url": (
                f"/media/{post.image.name}" if post.image else None
            ),
            "published_at": post.published_at,
            "published_at_str": (
                post.published_at.strftime("%Y-%m-%d %H:%M UTC")
                if post.published_at
                else ""
            ),
            "canonical_url": post.canonical_url,
            "syndication_urls": post.syndication_urls,
            "is_long": post.is_long,
            "is_micro": post.is_micro,
            "webmentions": webmentions,
        }

    def _fetch_webmentions(self, site_dir, rendered_posts):
        if not settings.WEBMENTION_IO_TOKEN:
            return

        domain = settings.SITE_DOMAIN
        token = settings.WEBMENTION_IO_TOKEN

        for post in rendered_posts:
            url = f"https://{domain}/posts/{post['uuid']}/"
            try:
                resp = requests.get(
                    "https://webmention.io/api/mentions",
                    params={"token": token, "target": url, "per-page": 50},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    post["webmentions"] = [
                        {
                            "source": m.get("source"),
                            "author_name": (
                                m.get("author", {}).get("name") or "Anonymous"
                            ),
                            "author_url": m.get("author", {}).get("url"),
                            "avatar": m.get("author", {}).get("photo"),
                            "content": m.get("content", {}).get("text"),
                            "published": m.get("published"),
                        }
                        for m in data.get("links", [])
                    ]
            except requests.RequestException as e:
                logger.warning("Failed to fetch webmentions for %s: %s", url, e)

        try:
            resp = requests.get(
                "https://webmention.io/api/mentions",
                params={"token": token, "target": f"https://{domain}/", "per-page": 50},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                data_path = site_dir / "webmentions.json"
                data_path.write_text(json.dumps(data.get("links", [])))
        except requests.RequestException as e:
            logger.warning("Failed to fetch page webmentions: %s", e)
