import uuid

from django.db import models


class Post(models.Model):
    class PostType(models.TextChoices):
        LONG = "long", "Long-form"
        MICRO = "micro", "Micro-post"

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post_type = models.CharField(
        max_length=5,
        choices=PostType.choices,
        default=PostType.MICRO,
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    body = models.TextField()
    image = models.ImageField(upload_to="images/", blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)
    is_published = models.BooleanField(default=False)
    syndication_urls = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        if self.post_type == self.PostType.LONG and self.title:
            return self.title
        body_preview = self.body[:60]
        if len(self.body) > 60:
            body_preview += "..."
        return body_preview

    @property
    def canonical_url(self):
        return f"https://{self._site_domain()}/posts/{self.uuid}/"

    @property
    def is_long(self):
        return self.post_type == self.PostType.LONG

    @property
    def is_micro(self):
        return self.post_type == self.PostType.MICRO

    @staticmethod
    def _site_domain():
        from django.conf import settings

        return settings.SITE_DOMAIN

    def syndicate(self):
        from posts.syndication.bluesky import syndicate_to_bluesky
        from posts.syndication.mastodon import syndicate_to_mastodon

        urls = {}
        try:
            bsky_url = syndicate_to_bluesky(self)
            if bsky_url:
                urls["bluesky"] = bsky_url
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error("Bluesky syndication failed: %s", e)

        try:
            mast_url = syndicate_to_mastodon(self)
            if mast_url:
                urls["mastodon"] = mast_url
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error("Mastodon syndication failed: %s", e)

        if urls:
            self.syndication_urls = urls
            self.save(update_fields=["syndication_urls"])


class HandleCache(models.Model):
    handle = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)

    bluesky_did = models.CharField(max_length=200, blank=True)
    bluesky_handle = models.CharField(max_length=200, blank=True)

    mastodon_acct = models.CharField(max_length=200, blank=True)
    mastodon_url = models.URLField(max_length=500, blank=True)
    mastodon_id = models.CharField(max_length=100, blank=True)

    resolved_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Handle cache"
        ordering = ["handle"]

    def __str__(self):
        return self.handle

    @property
    def is_fully_resolved(self):
        return bool(self.bluesky_did or self.mastodon_id)
