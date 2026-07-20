"""
Profil utilisateur — extension ADDITIVE de `auth.User` en OneToOne.

Choix d'architecture (voir audit) : on NE change PAS `AUTH_USER_MODEL` (les
données existent déjà sous `auth.User`, migrations `swappable_dependency` →
un swap serait destructif en prod). Le profil porte les métadonnées non
présentes sur `auth.User` (téléphone, fonction, organisation, préférences).
Le RBAC reste assuré par les groupes/permissions Django (déjà en place).
"""
from django.conf import settings
from django.db import models


class Profile(models.Model):
    LANG_CHOICES = [("fr", "Français"), ("en", "English")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile",
    )
    phone = models.CharField("Téléphone", max_length=32, blank=True)
    job_title = models.CharField("Fonction", max_length=120, blank=True)
    organization = models.CharField("Organisation", max_length=150, blank=True)
    department = models.CharField("Département", max_length=120, blank=True)
    language = models.CharField("Langue", max_length=8, choices=LANG_CHOICES, default="fr")
    timezone = models.CharField("Fuseau horaire", max_length=64, default="Africa/Abidjan")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"Profil de {self.user}"
