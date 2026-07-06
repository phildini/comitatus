import json

from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

from posts.forms import PostForm
from posts.models import HandleCache, Post
from posts.syndication.resolve import resolve_mentions, search_handles, select_handle


@login_required(login_url="/admin/login/")
def compose(request, pk=None):
    post = None
    if pk:
        post = get_object_or_404(Post, pk=pk)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            obj = form.save(commit=False)

            is_publish = request.POST.get("action") == "publish"

            if is_publish:
                obj.is_published = True
                obj.save()
                resolve_mentions(obj.body)
                obj.syndicate()
                call_command("build_site")
                messages.success(
                    request,
                    "Published!",
                )
                return redirect("compose")
            else:
                obj.is_published = False
                obj.save()
                resolve_mentions(obj.body)
                messages.info(request, "Draft saved.")
                return redirect("compose_edit", pk=obj.pk)
    else:
        form = PostForm(instance=post)

    return render(
        request,
        "posts/compose.html",
        {
            "form": form,
            "post": post,
            "drafts": Post.objects.filter(is_published=False).order_by(
                "-updated_at"
            )[:5],
        },
    )


@login_required(login_url="/admin/login/")
def draft_list(request):
    drafts = Post.objects.filter(is_published=False).order_by("-updated_at")
    return render(
        request,
        "posts/draft_list.html",
        {"drafts": drafts},
    )


@login_required(login_url="/admin/login/")
def search_handles_view(request):
    q = request.GET.get("q", "")
    if len(q) < 2:
        return JsonResponse([], safe=False)
    results = search_handles(q)
    return JsonResponse(results, safe=False)


@login_required(login_url="/admin/login/")
def select_handle_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    handle = data.get("handle", "")
    if not handle:
        return JsonResponse({"error": "handle required"}, status=400)

    select_handle(handle, data)
    return JsonResponse({"status": "ok"})


@login_required(login_url="/admin/login/")
def handle_status_view(request):
    handle = request.GET.get("handle", "").lower().lstrip("@")
    if not handle:
        return JsonResponse({"error": "handle required"}, status=400)

    cached = HandleCache.objects.filter(handle__iexact=handle).first()
    if not cached:
        return JsonResponse(
            {
                "handle": handle,
                "display_name": "",
                "bluesky": {"resolved": False, "handle": ""},
                "mastodon": {"resolved": False, "acct": ""},
            }
        )

    return JsonResponse(
        {
            "handle": cached.handle,
            "display_name": cached.display_name,
            "bluesky": {
                "resolved": bool(cached.bluesky_did),
                "handle": cached.bluesky_handle,
            },
            "mastodon": {
                "resolved": bool(cached.mastodon_id),
                "acct": cached.mastodon_acct,
            },
        }
    )
