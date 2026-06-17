from django import forms

from posts.models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["post_type", "title", "body", "image"]
        widgets = {
            "post_type": forms.RadioSelect(
                choices=Post.PostType.choices,
                attrs={"class": "post-type-toggle"},
            ),
            "body": forms.Textarea(
                attrs={
                    "rows": 12,
                    "class": "compose-body",
                    "placeholder": "What's on your mind?",
                }
            ),
            "image": forms.FileInput(attrs={"class": "compose-image"}),
        }
        labels = {
            "post_type": "Post type",
            "body": "",
        }

    def clean_body(self):
        body = self.cleaned_data.get("body")
        if body and len(body.encode("utf-8")) > 500:
            raise forms.ValidationError(
                "Post must be 500 characters or fewer (Mastodon limit)."
            )
        return body

    def clean(self):
        cleaned = super().clean()
        post_type = cleaned.get("post_type")
        title = cleaned.get("title")
        image = cleaned.get("image")

        if post_type == Post.PostType.LONG and not title:
            self.add_error("title", "Title is required for long-form posts.")

        if post_type == Post.PostType.LONG and image:
            self.add_error("image", "Images are only supported for micro-posts.")

        return cleaned
