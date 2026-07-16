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

from django.contrib.auth.models import Permission, User
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
        # `user` : authentifié SANS aucune permission métier (lecteur).
        cls.user = User.objects.create_user("testeur", password="pwd-test-2026")
        cls.superuser = User.objects.create_superuser(
            "admin-test", "admin@test.local", "pwd-admin-2026",
        )
        # `manager` : permissions add/change/delete_programorthophoto
        # explicites (et non superuser) pour prouver que ce sont bien
        # ces permissions précises qui débloquent les actions.
        cls.manager = User.objects.create_user("gestionnaire", password="pwd-mgr-2026")
        cls.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="parcelaire",
            codename__in=[
                "add_programorthophoto",
                "change_programorthophoto",
                "delete_programorthophoto",
            ],
        ))

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

    def test_command_masque_pour_lecteur(self):
        # Le champ `command` (commandes shell + chemins serveur) ne doit
        # pas fuiter vers un simple lecteur sans permission change_*.
        response = self.client.get(
            reverse("api-orthophoto-detail", args=[self.ortho_done.pk]),
        )
        log = response.json()["logs"][0]
        self.assertEqual(log["message"], "Reprojection OK")
        self.assertEqual(log["command"], "")

    def test_command_visible_pour_gestionnaire(self):
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("api-orthophoto-detail", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.json()["logs"][0]["command"], "gdalwarp ...")


class OrthophotoActionsPermissionTests(OrthophotoAPITestCase):
    """Un utilisateur authentifié SANS permission métier est refusé (403)
    sur toutes les actions mutantes/destructives, et rien n'est modifié."""

    def setUp(self):
        self.login()  # `testeur`, aucune permission

    @mock.patch("parcelaire.tasks.process_orthophoto.delay")
    def test_retry_refuse_sans_permission(self, delay):
        response = self.client.post(
            reverse("api-orthophoto-retry", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.status_code, 403)
        delay.assert_not_called()
        self.ortho_done.refresh_from_db()
        self.assertEqual(self.ortho_done.status, "DONE")

    def test_set_current_refuse_sans_permission(self):
        response = self.client.post(
            reverse("api-orthophoto-set-current", args=[self.ortho_pending.pk]),
        )
        self.assertEqual(response.status_code, 403)
        self.ortho_pending.refresh_from_db()
        self.assertFalse(self.ortho_pending.is_current)

    def test_delete_tiles_refuse_sans_permission(self):
        response = self.client.post(
            reverse("api-orthophoto-delete-tiles", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.status_code, 403)
        self.ortho_done.refresh_from_db()
        self.assertEqual(self.ortho_done.status, "DONE")
        self.assertTrue(self.ortho_done.tiles_url)

    def test_change_ne_suffit_pas_pour_delete_tiles(self):
        # delete-tiles exige delete_programorthophoto : un utilisateur
        # n'ayant QUE change_* est refusé.
        only_change = User.objects.create_user("changeur", password="x")
        only_change.user_permissions.add(Permission.objects.get(
            content_type__app_label="parcelaire",
            codename="change_programorthophoto",
        ))
        self.client.force_login(only_change)
        response = self.client.post(
            reverse("api-orthophoto-delete-tiles", args=[self.ortho_done.pk]),
        )
        self.assertEqual(response.status_code, 403)


class OrthophotoActionsAPITests(OrthophotoAPITestCase):
    def setUp(self):
        self.client.force_login(self.manager)

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
    tout appel S3 — testables sans MinIO. Connecté en gestionnaire :
    la permission add_* est vérifiée en amont (couverte ailleurs)."""

    def setUp(self):
        self.client.force_login(self.manager)
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


@mock.patch("parcelaire.services.storage.presign_part_url",
            return_value="http://minio.local/signed-part")
@mock.patch("parcelaire.services.storage.ensure_bucket_and_cors")
class UploadInitFlowTests(OrthophotoAPITestCase):
    """Chemin de succès et d'échec S3 de /orthophotos/upload/init/
    (stockage mocké — pas de MinIO requis)."""

    def setUp(self):
        self.url = reverse("orthophoto_upload_init")
        self.client.force_login(self.manager)

    def payload(self, **over):
        base = {
            "program": self.program.pk, "filename": "survol.tif",
            "total_size": 120 * 1024 * 1024,  # 120 Mo → 3 parts de 50 Mo
            "reference_year": 2026, "reference_month": 6,
        }
        base.update(over)
        return base

    @mock.patch("parcelaire.services.storage.initiate_multipart_upload",
                return_value="UPLOAD-ID-123")
    def test_init_succes_cree_session(self, initiate, *_):
        response = self.client.post(
            self.url, self.payload(), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["upload_id"], "UPLOAD-ID-123")
        self.assertEqual(len(data["parts"]), 3)  # ceil(120/50)
        ortho = ProgramOrthophoto.objects.get(pk=data["orthophoto_id"])
        self.assertEqual(ortho.status, "PENDING")
        self.assertEqual(ortho.metadata["s3_upload"]["upload_id"], "UPLOAD-ID-123")
        self.assertEqual(ortho.metadata["s3_upload"]["nb_parts"], 3)

    @mock.patch("parcelaire.services.storage.initiate_multipart_upload",
                side_effect=RuntimeError("MinIO down"))
    def test_init_echec_s3_renvoie_502_et_marque_failed(self, initiate, *_):
        response = self.client.post(
            self.url, self.payload(reference_month=7), content_type="application/json",
        )
        self.assertEqual(response.status_code, 502)
        ortho = ProgramOrthophoto.objects.filter(
            program=self.program, reference_year=2026, reference_month=7,
        ).first()
        self.assertIsNotNone(ortho)
        self.assertEqual(ortho.status, "FAILED")

    @mock.patch("parcelaire.services.storage.initiate_multipart_upload")
    def test_init_refuse_sans_permission_add(self, initiate, *_):
        self.client.force_login(self.user)  # `testeur`, pas de permission
        response = self.client.post(
            self.url, self.payload(), content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        initiate.assert_not_called()


class UploadCompleteAbortTests(OrthophotoAPITestCase):
    """/upload/complete/ et /upload/abort/ (stockage mocké)."""

    def setUp(self):
        self.client.force_login(self.manager)
        # Orthophoto avec une session d'upload S3 « en cours ».
        self.uploading = ProgramOrthophoto.objects.create(
            program=self.program, name="En cours",
            reference_year=2026, reference_month=9,
            status="PENDING",
            metadata={"s3_upload": {
                "key": "orthophotos/sources/50/survol.tif",
                "upload_id": "UP-9", "total_size": 100, "nb_parts": 1,
            }},
        )

    @mock.patch("parcelaire.tasks.process_orthophoto.delay")
    @mock.patch("parcelaire.services.storage.head_object",
                return_value={"ContentLength": 100})
    @mock.patch("parcelaire.services.storage.complete_multipart_upload")
    def test_complete_finalise_et_lance_celery(self, complete, head, delay):
        response = self.client.post(
            reverse("orthophoto_upload_complete"),
            {"orthophoto_id": self.uploading.pk,
             "parts": [{"PartNumber": 1, "ETag": "abc"}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        complete.assert_called_once()
        delay.assert_called_once_with(self.uploading.pk)

    def test_complete_sans_session_renvoie_400(self):
        response = self.client.post(
            reverse("orthophoto_upload_complete"),
            {"orthophoto_id": self.ortho_pending.pk, "parts": [{"x": 1}]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @mock.patch("parcelaire.services.storage.abort_multipart_upload")
    def test_abort_upload_en_cours_marque_failed(self, abort):
        response = self.client.post(
            reverse("orthophoto_upload_abort"),
            {"orthophoto_id": self.uploading.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        abort.assert_called_once()
        self.uploading.refresh_from_db()
        self.assertEqual(self.uploading.status, "FAILED")

    @mock.patch("parcelaire.services.storage.abort_multipart_upload")
    def test_abort_nepasse_pas_une_ortho_done_en_failed(self, abort):
        # Régression : abort sur une orthophoto DONE ne doit RIEN casser.
        response = self.client.post(
            reverse("orthophoto_upload_abort"),
            {"orthophoto_id": self.ortho_done.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("skipped"))
        abort.assert_not_called()
        self.ortho_done.refresh_from_db()
        self.assertEqual(self.ortho_done.status, "DONE")

    def test_abort_refuse_sans_permission_add(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("orthophoto_upload_abort"),
            {"orthophoto_id": self.uploading.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


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


# =====================================================================
# API CRUD + tableau de bord (parcelaire/api/crud.py, dashboard.py)
# =====================================================================
from parcelaire.models import Customer  # noqa: E402


class CrudAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = User.objects.create_user("crud-reader", password="pwd")
        cls.editor = User.objects.create_user("crud-editor", password="pwd")
        cls.editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="parcelaire",
            codename__in=[
                "add_customer", "change_customer", "delete_customer",
                "add_projetimmobilier", "change_projetimmobilier",
            ],
        ))
        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(code="P1", nom="Projet 1", country=cls.country)
        cls.customer = Customer.objects.create(
            customer_type="INDIVIDUAL", first_name="Awa", last_name="Koné", phone="0700",
        )

    def test_auth_required(self):
        self.assertEqual(self.client.get(reverse("api-dashboard")).status_code, 403)
        self.assertEqual(self.client.get("/api/crud/customers/").status_code, 403)

    def test_dashboard_counts(self):
        self.client.force_login(self.reader)
        data = self.client.get(reverse("api-dashboard")).json()
        self.assertIn("counts", data)
        self.assertEqual(data["counts"]["projects"], 1)
        self.assertEqual(data["counts"]["customers"], 1)

    def test_dashboard_masks_finance_without_permission(self):
        self.client.force_login(self.reader)
        data = self.client.get(reverse("api-dashboard")).json()
        self.assertFalse(data["can_view_financial"])
        self.assertEqual(data["finance"]["ca_total"], "Masqué")

    def test_list_paginated_and_searchable(self):
        self.client.force_login(self.reader)
        data = self.client.get("/api/crud/customers/").json()
        self.assertIn("results", data)
        self.assertEqual(data["count"], 1)
        # recherche
        empty = self.client.get("/api/crud/customers/?search=introuvable").json()
        self.assertEqual(empty["count"], 0)

    def test_create_requires_add_permission(self):
        self.client.force_login(self.reader)  # aucune permission
        resp = self.client.post(
            "/api/crud/customers/",
            {"customer_type": "INDIVIDUAL", "first_name": "X"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_update_delete_with_permission(self):
        self.client.force_login(self.editor)
        # create
        resp = self.client.post(
            "/api/crud/customers/",
            {"customer_type": "COMPANY", "company_name": "ACME SARL", "phone": "0102"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        cid = resp.json()["id"]
        self.assertEqual(resp.json()["display_name"], "ACME SARL")
        # update (PATCH)
        resp = self.client.patch(
            f"/api/crud/customers/{cid}/",
            {"company_name": "ACME Holding"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["company_name"], "ACME Holding")
        # delete = soft-delete (is_active=False)
        resp = self.client.delete(f"/api/crud/customers/{cid}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Customer.objects.get(pk=cid).is_active)
        # n'apparaît plus dans la liste (queryset is_active=True)
        self.assertEqual(self.client.get("/api/crud/customers/").json()["count"], 1)

    def test_program_slug_autogenerated_on_create(self):
        self.editor.user_permissions.add(Permission.objects.get(
            content_type__app_label="parcelaire", codename="add_realestateprogram",
        ))
        self.client.force_login(self.editor)
        resp = self.client.post(
            "/api/crud/programs/",
            {"code": "PRG-X", "name": "Programme X", "project": self.project.id,
             "country": self.country.id},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(RealEstateProgram.objects.get(code="PRG-X").slug, "programme-x")

    def test_options_endpoint(self):
        self.client.force_login(self.editor)
        data = self.client.get(reverse("api-crud-options")).json()
        self.assertTrue(data["permissions"]["customer"]["add"])
        self.assertFalse(data["permissions"]["program"]["delete"])
        self.assertTrue(any(o["value"] == "INDIVIDUAL" for o in data["customer_types"]))
