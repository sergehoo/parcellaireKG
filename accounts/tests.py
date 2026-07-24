from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Profile

User = get_user_model()


class ProfileTests(TestCase):
    def test_profile_created_automatically(self):
        u = User.objects.create_user("alice", password="pwd")
        self.assertTrue(Profile.objects.filter(user=u).exists())
        self.assertEqual(u.profile.language, "fr")
        self.assertEqual(u.profile.timezone, "Africa/Abidjan")

    def test_profile_str(self):
        u = User.objects.create_user("bob", password="pwd")
        self.assertIn("bob", str(u.profile))

    def test_no_duplicate_profile_on_resave(self):
        u = User.objects.create_user("carol", password="pwd")
        u.first_name = "Carol"
        u.save()  # ne doit pas recréer / dupliquer le profil
        self.assertEqual(Profile.objects.filter(user=u).count(), 1)

    def test_authentication_backends_include_allauth(self):
        from django.conf import settings
        self.assertIn(
            "allauth.account.auth_backends.AuthenticationBackend",
            settings.AUTHENTICATION_BACKENDS,
        )
        # AxesStandaloneBackend DOIT être en tête (anti-bruteforce), suivi de
        # ModelBackend (login username inchangé), puis allauth.
        self.assertEqual(
            settings.AUTHENTICATION_BACKENDS[0],
            "axes.backends.AxesStandaloneBackend",
        )
        self.assertIn(
            "django.contrib.auth.backends.ModelBackend",
            settings.AUTHENTICATION_BACKENDS,
        )
