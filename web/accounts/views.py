"""Authentication and account management views."""
import logging

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from accounts.bluesky import verify_credentials
from accounts.forms import (
    BlueskyConnectForm,
    InstanceUrlForm,
    LoginForm,
    SignupForm,
)
from accounts.mastodon import (
    build_authorize_url,
    exchange_code,
    fetch_identity,
    register_instance_app,
)
from accounts.models import BlueskyAccount, MastodonAccount, User

logger = logging.getLogger(__name__)
signer = TimestampSigner()


def _rate_limited(request, exception=None):
    return render(request, "accounts/rate_limited.html", status=429)


@ratelimit(key="ip", rate="3/h", method="POST", block=True)
def signup(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            token = signer.sign(str(user.id))
            verify_url = request.build_absolute_uri(
                reverse("accounts:verify_email", args=[token])
            )
            subject = "Verify your email for LinkGnome"
            body = render_to_string("accounts/verify_email.txt", {
                "user": user,
                "verify_url": verify_url,
            })
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
            return render(request, "accounts/check_email.html", {"email": user.email})
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


def verify_email(request, token):
    try:
        user_id = signer.unsign(token, max_age=86400)
    except (SignatureExpired, BadSignature):
        return render(request, "accounts/verify_failed.html", {"expired": True})

    try:
        user = User.objects.get(id=user_id, email_verified=False)
    except User.DoesNotExist:
        return render(request, "accounts/verify_failed.html", {"expired": False})

    user.email_verified = True
    user.save(update_fields=["email_verified"])
    return render(request, "accounts/verify_success.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(request.GET.get("next", "/"))
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("/accounts/login/")


@login_required
def settings_view(request):
    user = request.user
    mastodon = getattr(user, "mastodon_account", None)
    bluesky = getattr(user, "bluesky_account", None)

    return render(request, "accounts/settings.html", {
        "mastodon": mastodon,
        "bluesky": bluesky,
        "user": user,
    })


@login_required
def connect_mastodon(request):
    if not request.user.is_fully_activated:
        return redirect("accounts:settings")

    if getattr(request.user, "mastodon_account", None):
        return redirect("accounts:settings")

    if request.method == "POST":
        form = InstanceUrlForm(request.POST)
        if form.is_valid():
            instance_url = form.cleaned_data["instance_url"]
            callback_url = request.build_absolute_uri(
                reverse("accounts:mastodon_callback")
            )
            try:
                app = register_instance_app(instance_url, callback_url)
            except Exception as e:
                logger.exception("Failed to register app with %s", instance_url)
                form.add_error("instance_url", f"Failed to register with this instance: {e}")
                return render(request, "accounts/connect_mastodon.html", {"form": form})

            auth_url = build_authorize_url(
                instance_url, app["client_id"], callback_url
            )
            request.session["mastodon_state"] = {
                "instance_url": instance_url,
                "client_id": app["client_id"],
                "client_secret": app["client_secret"],
            }
            return HttpResponseRedirect(auth_url)
    else:
        form = InstanceUrlForm()

    return render(request, "accounts/connect_mastodon.html", {"form": form})


@login_required
def mastodon_callback(request):
    state = request.session.pop("mastodon_state", None)
    if not state:
        return redirect("accounts:settings")

    code = request.GET.get("code")
    if not code:
        return redirect("accounts:settings")

    callback_url = request.build_absolute_uri(reverse("accounts:mastodon_callback"))
    try:
        token_data = exchange_code(
            state["instance_url"],
            state["client_id"],
            state["client_secret"],
            code,
            callback_url,
        )
        identity = fetch_identity(state["instance_url"], token_data["access_token"])
    except Exception as e:
        logger.exception("Mastodon OAuth callback failed")
        return render(request, "accounts/connect_failed.html", {
            "platform": "Mastodon",
            "error": str(e),
        })

    MastodonAccount.objects.update_or_create(
        user=request.user,
        defaults={
            "instance_url": state["instance_url"],
            "access_token": token_data["access_token"],
            "mastodon_user_id": str(identity["id"]),
            "mastodon_username": identity.get("username", ""),
            "is_active": True,
        },
    )
    return redirect("feeds:dashboard")


@login_required
def connect_bluesky(request):
    if not request.user.is_fully_activated:
        return redirect("accounts:settings")

    if getattr(request.user, "bluesky_account", None):
        return redirect("accounts:settings")

    if request.method == "POST":
        form = BlueskyConnectForm(request.POST)
        if form.is_valid():
            handle = form.cleaned_data["handle"]
            app_password = form.cleaned_data["app_password"]
            try:
                session = verify_credentials(handle, app_password)
            except Exception as e:
                logger.exception("Bluesky verification failed")
                form.add_error(None, f"Verification failed: {e}")
                return render(request, "accounts/connect_bluesky.html", {"form": form})

            BlueskyAccount.objects.update_or_create(
                user=request.user,
                defaults={
                    "handle": handle,
                    "app_password": app_password,
                    "did": session.get("did", ""),
                    "is_active": True,
                },
            )
            return redirect("feeds:dashboard")
    else:
        form = BlueskyConnectForm()

    return render(request, "accounts/connect_bluesky.html", {"form": form})


@login_required
def disconnect_mastodon(request):
    if request.method == "POST":
        account = getattr(request.user, "mastodon_account", None)
        if account:
            account.delete()
    return redirect("accounts:settings")


@login_required
def disconnect_bluesky(request):
    if request.method == "POST":
        account = getattr(request.user, "bluesky_account", None)
        if account:
            account.delete()
    return redirect("accounts:settings")
