import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def syndicate_to_bluesky(post):
    if not settings.BLUESKY_USERNAME or not settings.BLUESKY_PASSWORD:
        logger.warning("Bluesky credentials not configured")
        return None

    from atproto import Client

    client = Client()
    client.login(settings.BLUESKY_USERNAME, settings.BLUESKY_PASSWORD)

    if post.is_long:
        text = f"{post.title}\n\n{post.canonical_url}"
    else:
        text = post.body
        if post.image:
            text = f"{text}\n\n{post.canonical_url}"

    result = client.send_post(text)
    return str(result.uri)
