import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from posts.models import Post

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Publish any posts that are past their scheduled time"

    def handle(self, *args, **options):
        now = timezone.now()
        pending = Post.objects.filter(
            is_published=False,
            published_at__isnull=False,
            published_at__lte=now,
        )

        count = pending.count()
        if count == 0:
            self.stdout.write("No posts to publish")
            return

        for post in pending:
            post.is_published = True
            post.save(update_fields=["is_published"])
            post.syndicate()
            self.stdout.write(f"Published: {post}")

        from django.core.management import call_command

        call_command("build_site")

        self.stdout.write(self.style.SUCCESS(f"Published {count} scheduled posts"))
