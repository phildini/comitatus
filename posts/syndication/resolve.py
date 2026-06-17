import logging
import re

import requests
from django.conf import settings

from posts.models import HandleCache

logger = logging.getLogger(__name__)

BLUESKY_SEARCH_URL = (
    "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActorsTypeahead"
)


def search_handles(query):
    results = []

    for cached in HandleCache.objects.filter(handle__istartswith=query):
        if cached.bluesky_did:
            results.append(
                {
                    "handle": cached.bluesky_handle or cached.handle,
                    "display_name": cached.display_name or cached.handle,
                    "platform": "bluesky",
                    "did": cached.bluesky_did,
                    "avatar_url": cached.avatar_url,
                    "is_cached": True,
                }
            )
        if cached.mastodon_id:
            results.append(
                {
                    "handle": cached.mastodon_acct or cached.handle,
                    "display_name": cached.display_name or cached.handle,
                    "platform": "mastodon",
                    "id": cached.mastodon_id,
                    "avatar_url": cached.avatar_url,
                    "is_cached": True,
                }
            )

    try:
        resp = requests.get(
            BLUESKY_SEARCH_URL,
            params={"q": query, "limit": 5},
            timeout=5,
        )
        if resp.status_code == 200:
            for actor in resp.json().get("actors", []):
                if not any(
                    r.get("did") == actor.get("did")
                    for r in results
                    if r.get("platform") == "bluesky"
                ):
                    results.append(
                        {
                            "handle": actor.get("handle", ""),
                            "display_name": actor.get("displayName")
                            or actor.get("handle", ""),
                            "platform": "bluesky",
                            "did": actor.get("did", ""),
                            "avatar_url": actor.get("avatar", ""),
                            "is_cached": False,
                        }
                    )
    except requests.RequestException as e:
        logger.warning("Bluesky search failed: %s", e)

    if settings.MASTODON_ACCESS_TOKEN:
        try:
            from mastodon import Mastodon

            mastodon = Mastodon(
                access_token=settings.MASTODON_ACCESS_TOKEN,
                api_base_url=settings.MASTODON_BASE_URL,
            )
            accounts = mastodon.account_search(query, limit=5)
            for acct in accounts:
                acct_handle = acct.get("acct", "")
                if "@" not in acct_handle:
                    domain = settings.MASTODON_BASE_URL.replace("https://", "")
                    acct_handle = f"{acct_handle}@{domain}"
                if not any(
                    r.get("id") == acct["id"]
                    for r in results
                    if r.get("platform") == "mastodon"
                ):
                    results.append(
                        {
                            "handle": acct_handle,
                            "display_name": acct.get("display_name")
                            or acct.get("username", ""),
                            "platform": "mastodon",
                            "id": acct["id"],
                            "avatar_url": acct.get("avatar", ""),
                            "is_cached": False,
                        }
                    )
        except Exception as e:
            logger.warning("Mastodon search failed: %s", e)

    return results


def select_handle(handle, platform_data):
    cached, _ = HandleCache.objects.get_or_create(
        handle__iexact=handle,
        defaults={"handle": handle},
    )

    if platform_data.get("display_name"):
        cached.display_name = platform_data["display_name"]
    if platform_data.get("avatar_url"):
        cached.avatar_url = platform_data["avatar_url"]

    if platform_data["platform"] == "bluesky":
        cached.bluesky_did = platform_data.get("did", "")
        cached.bluesky_handle = platform_data.get("handle", "")
    elif platform_data["platform"] == "mastodon":
        cached.mastodon_id = str(platform_data.get("id", ""))
        cached.mastodon_acct = platform_data.get("handle", "")
        cached.mastodon_url = platform_data.get("mastodon_url", "")

    cached.save()
    return cached


def resolve_mentions(body):
    mentions = re.findall(r"(?<![\w\/])@(\w+)", body)
    results = {}
    for handle in set(mentions):
        cached = HandleCache.objects.filter(handle__iexact=handle).first()
        if not cached:
            search_results = search_handles(handle)
            for r in search_results:
                if r["handle"].lower().startswith(handle.lower()):
                    cached = select_handle(handle, r)
                    break
        if cached:
            results[f"@{handle}"] = cached
    return results
