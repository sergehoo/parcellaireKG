"""
Tests de l'API REST orthophotos (parcelaire/api/orthophotos.py),
consommée par le frontend React (frontend/).

Couverture :
- authentification exigée sur tous les endpoints ;
- liste : filtres (projet, programme, année/mois, statut, recherche)
  et pagination ;
- détail : payload complet + logs ;
- actions : retry (Celery mocké), set-current (exclusivité par
  programme), delete-tiles ;
- reference-data : listes + permissions utilisateur ;
- validations de l'upload init (avant tout appel S3).
"""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from parcelaire.models import (
    Country,
    OrthophotoProcessingLog,
    ProgramOrthophoto,
    ProjetImmobilier,
    RealEstateProgram,
)


class OrthophotoAPITestCase(TestCase):
    """Socle commun : un projet, deux programmes, trois orthophotos."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("testeur", password="pwd-test-2026")
        cls.superuser = User.objects.create_superuser(
            "admin-test", "admin@test.local", "pwd-admin-2026",
        )

        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(
            code="PRJ-TEST", nom="Projet Test", country=cls.country,
        )
        cls.program = RealEstateProgram.objects.create(
            code="PRG-A", name="Programme A", slug="programme-a",
            country=cls.country, project=cls.project,
        )
        cls.other_program = RealEstateProgram.objects.create(
            code="PRG-B", name="Programme B", slug="programme-b",
            country=cls.country, project=cls.project,
        )

        cls.ortho_done = ProgramOrthophoto.objects.create(
            program=cls.program, name="Ortho mars",
            reference_year=2026, reference_month=3,
            status="DONE", progress_percent=100,
            tiles_url="/media/tiles_ortho/programme-a/2026/03/{z}/{x}/{y}.png",
            tiles_folder="tiles_ortho/programme-a/2026/03",
            is_current=True,
        )
        cls.ortho_pending = ProgramOrthophoto.objects.create(
            program=cls.program, name="Ortho avril",
            reference_year=2026, reference_month=4,
            status="PENDING",
        )
        cls.ortho_other = ProgramOrthophoto.objects.create(
            program=cls.other_program, name="Ortho B",
            reference_year=2026, reference_month=3,
            status="FAILED", error_message="gdal2tiles KO",
        )
        OrthophotoProcessingLog.objects.create(
            orthophoto=cls.ortho_done, level="INFO",
            message="Reprojection OK", command="gdalwarp ...",
        )

    def login(self):
        self.client.force_login(self.user)


class AuthRequiredTests(OrthophotoAPITestCase):
    def test_endpoints_refusent_les_anonymes(self):
        urls = [
            reverse("api-orthophoto-list"),
            reverse("api-orthophoto-refdata"),
            reverse("api-orthophoto-detail", args=[self.ortho_done.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, url)
        for name in ("api-orthophoto-retry", "api-orthophoto-set-current",
                     "api-orthophoto-delete-tiles"):
            response = self.client.post(reverse(name, args=[self.ortho_done.pk]))
            self.assertEqual(response.status_code, 403, name)


class OrthophotoListAPITests(OrthophotoAPITestCase):
    def setUp(self):
        self.login()

    def test_liste_complete(self):
        response = self.client.get(reverse("api-orthophoto-list"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 3)

    def test_filtre_programme(self):
        response = self.client.get(
            reverse("api-orthophoto-list"), {"program": self.program.pk},
        )
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertTrue(all(
            o["program"]["id"] == self.program.pk for o in data["results"]
        ))

    def test_filtre_projet_et_periode(self):
        response = self.client.get(
            reverse("api-orthophoto-list"),
            {"project": self.project.pk, "year": 2026, "month": 3},
        )
        data = response.json()
        self.assertEqual(data["count"], 2)

    def test_filtre_statut(self):
        response = self.client.get(
            reverse("api-orthophoto-list"), {"status": "FAILED"},
        )
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["id"], self.ortho_other.pk)

    def test_recherche_texte(self):
        response = self.client.get(reverse("api-orthophoto-list"), {"q": "avril"})
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Ortho avril")

    def test_pagination(self):
        response = self.client.get(
            reverse("api-orthophoto-list"), {"page_size": 2, "page": 2},
        )
        data = response.json()
        self.assertEqual(data["pages"], 2)
        self.assertEqual(data["page"], 2)
        self.assertEqual(len(data["results"]), 1)

    def test_page_size_borne_a_100(self):
        response = self.client.get(
            reverse("api-orthophoto-list"), {"page_size": 5000},
        )
        self.assertEqual(response.json()["page_size"], 100)

    def test_page_invalide_retombe_sur_1(self):
        response = self.client.get(
            reverse("api-orthophoto-list"), {"page": "abc"},
        )
        self.assertEqual(response.json()["page"], 1)


class OrthophotoDetailAPITests(OrthophotoAPITestCase):
    def setUp(self):
        self.login()

    def test_detail_et_logs(self):
        response = self.client.get(
            reverse("api-orthophoto-detail", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Ortho mars")
        self.assertEqual(data["status"], "DONE")
        self.assertTrue(data["is_current"])
        self.assertEqual(data["program"]["project"]["name"], "Projet Test")
        self.assertEqual(len(data["logs"]), 1)
        self.assertEqual(data["logs"][0]["message"], "Reprojection OK")

    def test_detail_404(self):
        response = self.client.get(reverse("api-orthophoto-detail", args=[999999]))
        self.assertEqual(response.status_code, 404)


class OrthophotoActionsAPITests(OrthophotoAPITestCase):
    def setUp(self):
        self.login()

    @mock.patch("parcelaire.tasks.process_orthophoto.delay")
    def test_retry_reinitialise_et_relance(self, delay):
        response = self.client.post(
            reverse("api-orthophoto-retry", args=[self.ortho_other.pk]),
        )
        self.assertEqual(response.status_code, 200)
        delay.assert_called_once_with(self.ortho_other.pk)
        self.ortho_other.refresh_from_db()
        self.assertEqual(self.ortho_other.status, "PENDING")
        self.assertEqual(self.ortho_other.progress_percent, 0)
        self.assertIsNone(self.ortho_other.error_message)

    @mock.patch("parcelaire.tasks.process_orthophoto.delay",
                side_effect=OSError("redis down"))
    def test_retry_celery_injoignable_renvoie_202(self, delay):
        response = self.client.post(
            reverse("api-orthophoto-retry", args=[self.ortho_other.pk]),
        )
        self.assertEqual(response.status_code, 202)
        self.ortho_other.refresh_from_db()
        self.assertEqual(self.ortho_other.status, "PENDING")

    def test_set_current_exclusif_par_programme(self):
        response = self.client.post(
            reverse("api-orthophoto-set-current", args=[self.ortho_pending.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.ortho_pending.refresh_from_db()
        self.ortho_done.refresh_from_db()
        self.ortho_other.refresh_from_db()
        self.assertTrue(self.ortho_pending.is_current)
        self.assertFalse(self.ortho_done.is_current)
        # L'autre programme n'est pas affecté.
        self.assertFalse(self.ortho_other.is_current)

    def test_delete_tiles_purge_et_repasse_pending(self):
        response = self.client.post(
            reverse("api-orthophoto-delete-tiles", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.ortho_done.refresh_from_db()
        self.assertIsNone(self.ortho_done.tiles_url)
        self.assertIsNone(self.ortho_done.tiles_folder)
        self.assertEqual(self.ortho_done.status, "PENDING")
        self.assertEqual(self.ortho_done.progress_percent, 0)


class ReferenceDataAPITests(OrthophotoAPITestCase):
    def test_listes_et_permissions(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("api-orthophoto-refdata"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([p["name"] for p in data["projects"]], ["Projet Test"])
        self.assertEqual(len(data["programs"]), 2)
        self.assertEqual(data["programs"][0]["project_id"], self.project.pk)
        self.assertEqual(len(data["statuses"]), 4)
        self.assertIn(3, data["months"])
        self.assertTrue(data["user"]["can_add"])

    def test_permissions_utilisateur_simple(self):
        self.login()
        data = self.client.get(reverse("api-orthophoto-refdata")).json()
        self.assertFalse(data["user"]["can_add"])
        self.assertEqual(data["user"]["username"], "testeur")

    def test_programme_inactif_exclu(self):
        self.other_program.is_active = False
        self.other_program.save()
        self.login()
        data = self.client.get(reverse("api-orthophoto-refdata")).json()
        self.assertEqual([p["name"] for p in data["programs"]], ["Programme A"])


class UploadInitValidationTests(OrthophotoAPITestCase):
    """Validations de POST /orthophotos/upload/init/ exécutées AVANT
    tout appel S3 — testables sans MinIO."""

    def setUp(self):
        self.login()
        self.url = reverse("orthophoto_upload_init")

    def post_json(self, payload):
        return self.client.post(self.url, payload, content_type="application/json")

    def test_program_obligatoire(self):
        response = self.post_json({"filename": "a.tif", "total_size": 10})
        self.assertEqual(response.status_code, 400)

    def test_programme_inconnu(self):
        response = self.post_json({
            "program": 999999, "filename": "a.tif", "total_size": 10,
        })
        self.assertEqual(response.status_code, 404)

    def test_extension_refusee(self):
        response = self.post_json({
            "program": self.program.pk, "filename": "a.jpg", "total_size": 10,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(".tif", response.json()["error"])

    def test_taille_obligatoire(self):
        response = self.post_json({
            "program": self.program.pk, "filename": "a.tif",
        })
        self.assertEqual(response.status_code, 400)

    def test_mois_invalide(self):
        response = self.post_json({
            "program": self.program.pk, "filename": "a.tif", "total_size": 10,
            "reference_year": 2026, "reference_month": 13,
        })
        self.assertEqual(response.status_code, 400)

    def test_conflit_periode_renvoie_409(self):
        response = self.post_json({
            "program": self.program.pk, "filename": "a.tif", "total_size": 10,
            "reference_year": 2026, "reference_month": 3,
        })
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertTrue(data["conflict"])
        self.assertEqual(data["existing_id"], self.ortho_done.pk)


class OrthophotoModelTests(OrthophotoAPITestCase):
    def test_une_seule_courante_par_programme(self):
        # Le save() du modèle exécute full_clean(), qui valide la
        # contrainte conditionnelle uniq_current_orthophoto_per_program :
        # créer une 2e « courante » sans décocher l'existante doit lever.
        # (C'est pour cela que la vue d'upload et l'API set-current
        # décochent d'abord les autres, dans la même transaction.)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            ProgramOrthophoto.objects.create(
                program=self.program, name="Ortho mai",
                reference_year=2026, reference_month=5,
                status="DONE", is_current=True,
            )

    def test_statut_api_json(self):
        self.login()
        response = self.client.get(
            reverse("orthophoto_status", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "DONE")
        self.assertEqual(len(data["logs"]), 1)
