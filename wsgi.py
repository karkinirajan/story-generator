"""Production entry point: ``gunicorn wsgi:app``."""

import logging
import os

from dotenv import load_dotenv

from storylens import create_app

load_dotenv()
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL") or "INFO",
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
app = create_app()
