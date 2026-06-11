import logging

from django.core.management.base import BaseCommand

from posts.models import Post

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Resyndicate all published posts to Bluesky and Mastodon"

    def add_arguments(self, parser):
        parser.add_argument(
            "--post",
            type=str,
            help="UUID of a specific post to resyndicate",
        )

    def handle(self, *args, **options):
        if options["post"]:
            posts = Post.objects.filter(
                uuid=options["post"],
                is_published=True,
            )
        else:
            posts = Post.objects.filter(is_published=True)

        count = posts.count()
        if count == 0:
            self.stdout.write("No published posts to syndicate")
            return

        for post in posts:
            self.stdout.write(f"Syndicating: {post}")
            post.syndicate()

        self.stdout.write(self.style.SUCCESS(f"Syndicated {count} posts"))
