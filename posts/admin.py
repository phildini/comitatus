from django.contrib import admin
from django.utils.html import format_html

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "post_type",
        "is_published",
        "published_at",
        "syndication_links",
    ]
    list_filter = ["post_type", "is_published"]
    search_fields = ["title", "body"]
    date_hierarchy = "published_at"
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "post_type",
                    "title",
                    "body",
                    "image",
                ]
            },
        ),
        (
            "Publishing",
            {
                "fields": [
                    "is_published",
                    "published_at",
                    "syndication_urls",
                ]
            },
        ),
    ]
    readonly_fields = ["syndication_urls"]

    def save_model(self, request, obj, form, change):
        was_published = Post.objects.filter(pk=obj.pk).values_list(
            "is_published", flat=True
        )
        was_published = was_published.first() if was_published else False

        super().save_model(request, obj, form, change)

        if obj.is_published and not was_published:
            obj.syndicate()
            self._build_site(request)

    def syndication_links(self, obj):
        if not obj.syndication_urls:
            return "—"
        links = []
        for platform, url in obj.syndication_urls.items():
            links.append(f'<a href="{url}" target="_blank">{platform}</a>')
        return format_html(" | ".join(links))

    syndication_links.short_description = "Syndication"

    actions = ["resyndicate", "rebuild_site"]

    def resyndicate(self, request, queryset):
        for post in queryset.filter(is_published=True):
            post.syndicate()
        self.message_user(request, f"Resyndicated {queryset.count()} posts.")

    resyndicate.short_description = "Resyndicate selected posts"

    def rebuild_site(self, request, queryset):
        from django.core.management import call_command

        call_command("build_site")
        self.message_user(request, "Site rebuilt and deployed.")

    rebuild_site.short_description = "Rebuild and deploy the static site"

    def _build_site(self, request):
        from django.core.management import call_command

        try:
            call_command("build_site")
        except Exception as e:
            from django.contrib import messages

            messages.error(request, f"Site build failed: {e}")
