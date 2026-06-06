"""Authentication forms."""
from django import forms


class InstanceUrlForm(forms.Form):
    instance_url = forms.URLField(
        widget=forms.URLInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "https://mastodon.social",
        }),
        label="Mastodon Instance URL",
    )

    def clean_instance_url(self):
        url = self.cleaned_data["instance_url"].rstrip("/")
        if not url.startswith("http"):
            url = f"https://{url}"
        return url


class BlueskyConnectForm(forms.Form):
    handle = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "user.bsky.social",
        }),
        label="Bluesky Handle",
    )
    app_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "input input-bordered w-full",
        }),
        label="App Password",
        help_text="Create an app password at bsky.app/settings/app-passwords",
    )
