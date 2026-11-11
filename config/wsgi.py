"""
WSGI config for Dulce Arte project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.wsgi import get_wsgi_application

base_dir = Path(__file__).resolve().parent.parent
load_dotenv(base_dir / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_wsgi_application()
