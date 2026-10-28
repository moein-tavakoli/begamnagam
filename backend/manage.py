#!/usr/bin/env python
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Isolated automated checks get fresh, inherited environment values, never
# product credentials or a shared hardcoded key. This cannot start a server.
if (os.environ.get("DJANGO_TESTING") == "1" and len(sys.argv) > 1
        and sys.argv[1] in {"test", "check", "makemigrations"}):
    from config.ephemeral_environment import prepare_ephemeral_secrets
    prepare_ephemeral_secrets()
from django.core.management import execute_from_command_line

execute_from_command_line(sys.argv)
