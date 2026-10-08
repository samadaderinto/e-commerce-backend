"""Server-observed activity, with bounded writes and no profile timestamp changes."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import User
from store.models import Store


def record_activity(user: User) -> None:
    now = timezone.now()
    cutoff = now - timedelta(minutes=5)
    stale = Q(last_active_at__isnull=True) | Q(last_active_at__lt=cutoff)
    changed = User.objects.filter(stale, pk=user.pk).update(last_active_at=now)
    Store.objects.filter(stale).filter(Q(user=user) | Q(assigned_staff=user)).update(last_active_at=now)
    if changed:
        user.last_active_at = now


def record_store_activity(store: Store) -> None:
    now = timezone.now()
    stale = Q(last_active_at__isnull=True) | Q(last_active_at__lt=now - timedelta(minutes=5))
    if Store.objects.filter(stale, pk=store.pk).update(last_active_at=now):
        store.last_active_at = now
