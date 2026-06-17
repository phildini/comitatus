import logging
import re

from atproto import Client, models
from django.conf import settings

from posts.models import HandleCache

logger = logging.getLogger(__name__)


def _build_facets(text):
    facets = []
    for match in re.finditer(r"(?<![\w\/])@(\w+)", text):
        handle = match.group(1)
        cached = HandleCache.objects.filter(handle__iexact=handle).first()
        if cached and cached.bluesky_did:
            byte_start = len(text[: match.start()].encode("utf-8"))
            byte_end = byte_start + len(match.group().encode("utf-8"))
            facets.append(
                models.AppBskyRichtextFacet.Main(
                    features=[
                        models.AppBskyRichtextFacet.Mention(did=cached.bluesky_did)
                    ],
                    index=models.AppBskyRichtextFacet.ByteSlice(
                        byteStart=byte_start,
                        byteEnd=byte_end,
                    ),
                )
            )
    return facets


def _split_thread(text, facets):
    if len(text.encode("utf-8")) <= 300:
        return [(text, facets)]

    parts = []
    remaining = text
    remaining_facets = list(facets)
    text_bytes = len(text.encode("utf-8"))

    while text_bytes > 300:
        split_at = remaining.rfind("\n\n", 0, 301)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, 301)
        if split_at == -1:
            split_at = 300

        part = remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()
        text_bytes = len(remaining.encode("utf-8"))

        part_bytes = len(part.encode("utf-8"))
        part_facets = []
        next_facets = []
        sep_len = len(remaining[:split_at].encode("utf-8")) - len(part.encode("utf-8"))

        for f in remaining_facets:
            if f.index.byteEnd <= part_bytes:
                part_facets.append(f)
            else:
                shift = part_bytes + sep_len
                f.index.byteStart -= shift
                f.index.byteEnd -= shift
                next_facets.append(f)

        remaining_facets = next_facets
        parts.append((part, part_facets))

    parts.append((remaining, remaining_facets))
    return parts


def syndicate_to_bluesky(post):
    if not settings.BLUESKY_USERNAME or not settings.BLUESKY_PASSWORD:
        logger.warning("Bluesky credentials not configured")
        return None

    client = Client()
    client.login(settings.BLUESKY_USERNAME, settings.BLUESKY_PASSWORD)

    if post.is_long:
        text = f"{post.title}\n\n{post.canonical_url}"
        result = client.send_post(text)
        return [str(result.uri)]

    text = post.body
    image_url = None
    if post.image:
        image_url = f"{post.canonical_url}{post.image.url}"

    facets = _build_facets(text)
    parts = _split_thread(text, facets)

    uris = []
    root_uri = None
    root_cid = None

    for i, (part_text, part_facets) in enumerate(parts):
        embed = None
        if i == 0 and image_url:
            embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    uri=post.canonical_url,
                    title=post.canonical_url,
                    description="",
                )
            )

        reply_ref = None
        if i > 0 and root_uri is not None:
            reply_ref = models.AppBskyFeedPost.ReplyRef(
                parent=models.ComAtprotoRepoStrongRef.Main(
                    uri=uris[-1], cid=""
                ),
                root=models.ComAtprotoRepoStrongRef.Main(
                    uri=root_uri, cid=root_cid or ""
                ),
            )

        result = client.send_post(
            text=part_text,
            facets=part_facets or None,
            reply_to=reply_ref,
            embed=embed,
        )

        uris.append(str(result.uri))

        if i == 0:
            root_uri = result.uri
            root_cid = result.cid

    return uris
