"""Adaptateur allauth : auto-inscription publique désactivée.

Les comptes sont provisionnés par un administrateur (admin Django / invitation).
Sans ce garde, `/accounts/signup/` (exposé par allauth.urls) permettait à tout
visiteur anonyme de créer un compte et d'obtenir immédiatement une session
authentifiée — donc l'accès à tous les endpoints protégés par `IsAuthenticated`.
"""
from allauth.account.adapter import DefaultAccountAdapter


class NoPublicSignupAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False
