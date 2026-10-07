"""
Alias command for populate_fake_data.
Allows developers to run `python manage.py seed_fake_data` or `python manage.py populate_fake_data`.
"""
from core.management.commands.populate_fake_data import Command

__all__ = ["Command"]
