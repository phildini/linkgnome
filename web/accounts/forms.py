"""Authentication forms."""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import User


class SignupForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"}),
        label="Password",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full"}),
        label="Confirm Password",
    )

    class Meta:
        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "input input-bordered w-full"}),
            "email": forms.EmailInput(attrs={"class": "input input-bordered w-full"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("confirm_password"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_active = True
        user.email_verified = False
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full", "autocomplete": "username"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input input-bordered w-full", "autocomplete": "current-password"})
    )


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
