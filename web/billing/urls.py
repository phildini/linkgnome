"""Billing URL configuration."""
from django.urls import path
from billing import views

app_name = "billing"

urlpatterns = [
    path("create-checkout/<int:price_id>/", views.create_checkout, name="create_checkout"),
    path("success/", views.checkout_success, name="success"),
    path("cancel/", views.checkout_cancel, name="cancel"),
]
