"""
WSGI config for codematics project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
"""

import os
import dotenv
import pathlib


from django.core.wsgi import get_wsgi_application


# acess .env file
CURRENT_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE_PATH = CURRENT_DIR / ".env.prod"
dotenv.read_dotenv(str(ENV_FILE_PATH))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codematics.settings")

application = get_wsgi_application()