# Smart Posting Interface & @-Tag Resolution

## Summary

A standalone compose page that replaces `/admin/` as the primary entry point, with
live @-tag resolution against Bluesky and Mastodon, automatic thread splitting
for long micro-posts, and a maintained handle cache.

---

## HandleCache Model

File: `posts/models.py` — new model

```python
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
```

One row per short `handle` key (e.g. `"phildini"`). Both Bluesky and
Mastodon identities live on the same row, populated incrementally as the
user clicks suggestions. Admin registered with search, list display, and
a "Resolve" admin action to re-fetch from both APIs.

---

## Handle Resolution Service

File: `posts/syndication/resolve.py` — new file

Two public functions:

### `search_handles(query: str) -> list[dict]`

Called by the AJAX endpoint when the user pauses at an @-handle.

1. Check local `HandleCache` for `handle__istartswith=query` → mark as
   `is_cached=True` in results
2. Query Bluesky: `Client().search_actors_typeahead(query)` → return
   handle, display_name, DID, avatar
3. Query Mastodon: `mastodon.account_search(query)` → return acct,
   display_name, ID, URL, avatar
4. Merge and return JSON-serializable list tagged by `platform`:
   ```json
   [
     {"handle": "phildini.bsky.social", "display_name": "Philip James",
      "platform": "bluesky", "did": "did:plc:...", "avatar_url": "...",
      "is_cached": true},
     {"handle": "@phildini@mastodon.social", "display_name": "Philip James",
      "platform": "mastodon", "id": "123456", "avatar_url": "...",
      "is_cached": false}
   ]
   ```

### `select_handle(handle: str, platform_data: dict) -> HandleCache`

Called when the user clicks a suggestion in the side pane.

1. `HandleCache.objects.get_or_create(handle__iexact=handle)`
2. Fill platform-specific fields based on `platform_data["platform"]`
3. Save and return

### `resolve_mentions(body: str) -> dict`

Called at draft-save time and publish time to warm/verify the cache.

1. Regex `r'(?<![\w\/])@(\w+)'` — find all @-handles in body
2. For each, `HandleCache.objects.filter(handle__iexact=match).first()`
3. If not found, call `search_handles(match)` and auto-select the first
   result per platform (transparent warmup, no UI)
4. Return `{ "@handle": cached_row, ... }`

---

## Compose View & Form

### URLs

File: `posts/urls.py` — new file

| URL | View | Methods | Purpose |
|---|---|---|---|
| `/compose/` | `compose` | GET, POST | New post form |
| `/compose/<uuid:pk>/` | `compose` | GET, POST | Edit existing post |
| `/compose/search-handles/` | `search_handles` | GET | AJAX: platform search |
| `/compose/select-handle/` | `select_handle` | POST | AJAX: cache selected |
| `/drafts/` | `draft_list` | GET | List unpublished posts |

All views decorated with `@login_required(login_url="/admin/login/")`.

File: `comitatus/urls.py` — add `path("", include("posts.urls"))` **before**
the admin redirect.

### Form

File: `posts/forms.py` — new file

```python
class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["post_type", "title", "body", "image"]
        widgets = {
            "post_type": forms.RadioSelect(choices=Post.PostType.choices),
            "body": forms.Textarea(attrs={"rows": 12, "class": "compose-body"}),
            "image": forms.FileInput(),
        }
```

Custom validation:
- `title` required when `post_type == "long"`
- `body` required always
- `image` only valid for `post_type == "micro"`
- `len(body.encode("utf-8")) <= 500` — hard character block at Mastodon's limit

### View logic

File: `posts/views.py` — new file

**`compose(request, pk=None)`**

- GET: if `pk` load existing `Post`, else empty `PostForm()`
- POST: validate form
  - If "Save Draft" pressed: `is_published=False`, save, call
    `resolve_mentions(body)` in background, redirect to `/compose/<uuid>/`
  - If "Publish" pressed: `is_published=True`, save, call
    `post.syndicate()` then `build_site`, redirect to confirmation banner

**`search_handles(request)`**

- `?q=...` query param
- If `len(q) < 2` return empty list
- Call `search_handles(q)`, return `JsonResponse(results)`

**`select_handle(request)`**

- POST with JSON body: `{ "handle", "platform", "did"/"id", "display_name", ... }`
- Call `select_handle(data["handle"], data)`
- Return `JsonResponse({"status": "ok"})`

**`draft_list(request)`**

- Query `Post.objects.filter(is_published=False).order_by("-updated_at")`
- Render `drafts.html` template with simple list

---

## Compose Page Template

File: `templates/posts/compose.html` — new file

### Layout

```
Two-column: editor (left, ~70%) + @-tag suggestions (right, ~30%).

Top nav bar with links:
  [New Post] [Drafts] [Handle Cache → /admin/...] [All Posts → /admin/...]

Editor column:
  - Post type radio toggle (Micro default)
  - Title input (hidden when micro, shown when long)
  - Body textarea (full width)
  - Image upload (hidden when long, shown when micro)
  - Character counter bar below textarea
  - [Save Draft] [Publish] buttons

Suggestions column:
  - Hidden by default
  - Appears when user pauses >500ms after typing @ + 2+ more chars
  - Shows cached results immediately (green checkmark badge)
  - Shows API results as they arrive (platform badge: Bluesky/Mastodon)
  - Each row: avatar(32px) | display_name | @handle | platform tag
  - Click = select → highlight green, populate HandleCache
  - Loading spinner while waiting for API
  - "Search failed" + retry link on error
```

### Character Counter

- Server-enforced max: 500 bytes (Mastodon limit)
- Display thresholds:
  - 0–250 chars: green bar
  - 250–300 chars: yellow bar (approaching Bluesky split)
  - 300–500 chars: red bar (will split into Bluesky thread)
  - 500: input blocked, visual indicator "Max length reached"
- Counter reads: `{chars} / 500 chars`

### @-Tag Highlighting

After resolution, already-cached @-tags in the textarea are visually
highlighted. Since we can't easily style textarea internals without a
rich text editor, the suggestion pane shows a "Resolved tags" section:

```
Resolved tags:
  ✓ @phildini → Bluesky · Mastodon
  ✓ @someuser → Bluesky
  ⚠ @unknown → Not found on either platform
```

Unresolved or failed tags get a warning. Clicking the warning re-triggers
search.

### Draft List

File: `templates/posts/draft_list.html` — new file

Simple table: title/preview, post_type, updated_at, edit link.
Empty state: "No drafts. [Write something] → /compose/"

---

## Syndication Changes

### `bluesky.py` — rewritten

```python
def syndicate_to_bluesky(post):
    # 1. Parse @-tags and build facets
    body = post.body
    facets = []
    for match in re.finditer(r'(?<![\w\/])@(\w+)', body):
        cached = HandleCache.objects.filter(handle__iexact=match.group(1)).first()
        if cached and cached.bluesky_did:
            byte_start = len(body[:match.start()].encode("utf-8"))
            byte_end = byte_start + len(match.group().encode("utf-8"))
            facets.append({
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [{
                    "$type": "app.bsky.richtext.facet#mention",
                    "did": cached.bluesky_did,
                }],
            })

    # 2. Thread splitting for >300 chars
    text = body
    if post.is_long:
        text = f"{post.title}\n\n{text}"

    parts = _split_bluesky_thread(text, facets)
    uris = []

    for i, (part_text, part_facets) in enumerate(parts):
        reply_to = uris[-1] if uris else None
        result = client.send_post(part_text, facets=part_facets or None,
                                  reply_to=reply_to)
        uris.append(str(result.uri))

    return uris  # list of URIs, store first as the "top" link
```

```python
def _split_bluesky_thread(text, facets):
    """Split text into ≤300-char segments at paragraph breaks."""
    if len(text.encode("utf-8")) <= 300:
        return [(text, facets)]

    parts = []
    remaining = text
    remaining_facets = list(facets)

    while len(remaining.encode("utf-8")) > 300:
        # Find paragraph break closest to but not exceeding 300
        split_at = remaining.rfind("\n\n", 0, 300)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, 300)
        if split_at == -1:
            split_at = 300

        part = remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()

        # Split facets by byte ranges
        part_bytes = len(part.encode("utf-8"))
        part_facets = []
        next_facets = []
        for f in remaining_facets:
            if f["index"]["byteEnd"] <= part_bytes:
                part_facets.append(f)
            else:
                # Offset remaining facet by part length + separator
                shift = part_bytes + 1  # +1 for removed newline
                f["index"]["byteStart"] -= shift
                f["index"]["byteEnd"] -= shift
                next_facets.append(f)
        remaining_facets = next_facets

        parts.append((part, part_facets))

    parts.append((remaining, remaining_facets))
    return parts
```

### `mastodon.py` — modified

Replace @-tag substitution and keep remaining logic:

```python
def _substitute_mentions(text):
    def replace(match):
        handle = match.group(1)
        cached = HandleCache.objects.filter(handle__iexact=handle).first()
        if cached and cached.mastodon_acct:
            return f"@{cached.mastodon_acct}"
        return match.group(0)

    return re.sub(r'(?<![\w\/])@(\w+)', replace, text)
```

### `Post.syndicate()` — modified

Store `syndication_urls` with top-level links only:

```python
def syndicate(self):
    urls = {}
    try:
        bsky_uris = syndicate_to_bluesky(self)
        if bsky_uris:
            urls["bluesky"] = bsky_uris[0]  # first = top of thread
    except Exception as e:
        logger.error("Bluesky syndication failed: %s", e)

    try:
        mast_url = syndicate_to_mastodon(self)
        if mast_url:
            urls["mastodon"] = mast_url
    except Exception as e:
        logger.error("Mastodon syndication failed: %s", e)

    if urls:
        self.syndication_urls = urls
        self.save(update_fields=["syndication_urls"])
```

---

## Static Site Changes

No structural changes. The existing `post.html` and `home.html` templates
already render `post.syndication_urls` as flat links. Since we now store
only the top Bluesky URI (a single string instead of an array), the
existing template logic works unchanged.

---

## Navigation & Edge Cases

### Navigation

`comitatus.fly.dev` redirects to `/compose/` instead of `/admin/`.
The compose page nav bar provides links to admin pages for management.

Root redirect in `comitatus/urls.py` updated:
```python
path("", lambda request: HttpResponseRedirect("/compose/"))
```

### Settings additions

```python
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/compose/"
```

### Edge Cases

| Scenario | Behavior |
|---|---|
| Publish with unresolvable @-tags | Warn in UI banner, skip that tag for that platform, proceed |
| One platform fails | Log error, succeed on the other, show partial failure banner |
| Edit published post + save | Treat as new publish — resyndicate, rebuild site |
| Draft saved with no @-tags | Just save, nothing to resolve |
| Micro-post exactly 300 chars | No split — one Bluesky post |
| Micro-post 301 chars | Split at paragraph/sentence break before 300 |
| API rate limited | Log error, mark failed for that platform, next publish retries |
| Handle resolves differently between draft and publish | Cached data is used at publish time (Option B approved). Re-resolve via admin action if needed |

### Confirmation Banner (post-publish)

```
✅ Published!
  View on phildini.net  |  Bluesky  |  Mastodon
```

Dismissible. Shown on the compose page after successful publish.

---

## Files Summary

### New files

| File | Lines (est.) |
|---|---|
| `posts/syndication/resolve.py` | ~100 |
| `posts/forms.py` | ~50 |
| `posts/views.py` | ~120 |
| `posts/urls.py` | ~15 |
| `templates/posts/compose.html` | ~150 |
| `templates/posts/draft_list.html` | ~30 |
| `static/css/compose.css` | ~80 |

### Modified files

| File | Change |
|---|---|
| `posts/models.py` | Add `HandleCache` model |
| `posts/admin.py` | Register `HandleCache`, add nav links |
| `posts/syndication/bluesky.py` | Rewrite: facets + thread splitting |
| `posts/syndication/mastodon.py` | Add @-tag substitution |
| `posts/models.py` (`Post.syndicate`) | Store single Bluesky URI |
| `comitatus/urls.py` | Add posts.urls include, change root redirect |
| `comitatus/settings.py` | Add `LOGIN_URL`, `LOGIN_REDIRECT_URL` |
