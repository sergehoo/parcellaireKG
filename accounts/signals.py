"""Création automatique du profil à la création d'un utilisateur."""
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile

User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="accounts_ensure_profile")
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
