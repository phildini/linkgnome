"""Test configuration for linkgnome-web."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_SECRET_KEY"] = "test-key-for-testing-purposes-only"
os.environ["DJANGO_DEBUG"] = "True"
os.environ["DATA_DIR"] = "/tmp/linkgnome-test-data"

import django
django.setup()
