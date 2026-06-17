import logging
import re

from django.conf import settings

from posts.models import HandleCache

logger = logging.getLogger(__name__)


def _substitute_mentions(text):
    def replace(match):
        handle = match.group(1)
        cached = HandleCache.objects.filter(handle__iexact=handle).first()
        if cached and cached.mastodon_acct:
            return f"@{cached.mastodon_acct}"
        return match.group(0)

    return re.sub(r"(?<![\w\/])@(\w+)", replace, text)


def syndicate_to_mastodon(post):
    if not settings.MASTODON_ACCESS_TOKEN or not settings.MASTODON_BASE_URL:
        logger.warning("Mastodon credentials not configured")
        return None

    from mastodon import Mastodon

    mastodon = Mastodon(
        access_token=settings.MASTODON_ACCESS_TOKEN,
        api_base_url=settings.MASTODON_BASE_URL,
    )

    if post.is_long:
        status = f"{post.title}\n\n{post.canonical_url}"
    else:
        status = post.body
        if post.image:
            status = f"{post.body}\n\n{post.canonical_url}"

    status = _substitute_mentions(status)

    media_ids = []
    if post.image and post.image.path:
        try:
            media = mastodon.media_post(post.image.path)
            media_ids.append(media["id"])
        except Exception as e:
            logger.warning("Failed to upload media to Mastodon: %s", e)

    result = mastodon.status_post(status, media_ids=media_ids or None)
    return result["url"]
