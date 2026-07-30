import json
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings

from ai_copilot import executor
from ai_copilot import gateway
from ai_copilot import tools as registry
from ai_copilot.agent import run_turn
from ai_copilot.models import CopilotConversation, CopilotToolCall
from parcelaire.models import Country, Customer, ProjetImmobilier, RealEstateProgram


class CopilotBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("copilot-user", password="pwd")  # aucun droit métier
        cls.finuser = User.objects.create_user("copilot-fin", password="pwd")
        cls.finuser.user_permissions.add(Permission.objects.get(
            content_type__app_label="parcelaire", codename="view_financial_data"))
        cls.piiuser = User.objects.create_user("copilot-pii", password="pwd")
        cls.piiuser.user_permissions.add(Permission.objects.get(
            content_type__app_label="parcelaire", codename="view_patient_data"))
        cls.customer = Customer.objects.create(
            customer_type="INDIVIDUAL", first_name="Awa", last_name="Koné")
        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(code="P1", nom="Projet 1", country=cls.country)
        cls.program = RealEstateProgram.objects.create(
            code="CAL", name="Callisto", slug="callisto",
            country=cls.country, project=cls.project,
            centroid=Point(-4.02, 5.35, srid=4326))  # (lng, lat) Abidjan


class ToolRegistryTests(CopilotBaseTestCase):
    def test_schemas_exposes_mvp_tools(self):
        names = {s["function"]["name"] for s in registry.schemas_for(self.user)}
        self.assertTrue({"search_entities", "get_dashboard_summary",
                         "focus_map_on_program", "generate_report"} <= names)


class ExecutorTests(CopilotBaseTestCase):
    def test_unknown_tool_journaled(self):
        res = executor.run_tool(self.user, "does_not_exist", {}, {})
        self.assertIn("error", res.content)
        self.assertTrue(CopilotToolCall.objects.filter(tool_name="does_not_exist",
                                                       status="unknown").exists())

    def test_dashboard_masks_finance_without_permission(self):
        res = executor.run_tool(self.user, "get_dashboard_summary", {}, {})
        self.assertEqual(res.content["finance"]["ca_total"], registry.MASKED)
        self.assertTrue(CopilotToolCall.objects.filter(
            tool_name="get_dashboard_summary", status="ok").exists())

    def test_dashboard_shows_finance_with_permission(self):
        res = executor.run_tool(self.finuser, "get_dashboard_summary", {}, {})
        self.assertNotEqual(res.content["finance"]["ca_total"], registry.MASKED)

    def test_geocode_place_returns_map_focus(self):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = [{"lat": "5.35", "lon": "-4.00",
                                   "display_name": "Cocody, Abidjan"}]
        with mock.patch("requests.get", return_value=fake):
            res = executor.run_tool(self.user, "geocode_place", {"place": "Cocody"}, {})
        self.assertEqual(res.action["type"], "map.focus")
        self.assertEqual(res.action["center"], [5.35, -4.00])

    def test_geocode_place_not_found(self):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = []
        with mock.patch("requests.get", return_value=fake):
            res = executor.run_tool(self.user, "geocode_place", {"place": "zzz"}, {})
        self.assertIn("error", res.content)
        self.assertIsNone(res.action)

    def test_focus_map_returns_action_with_center(self):
        res = executor.run_tool(self.user, "focus_map_on_program",
                                {"program_name": "Callisto"}, {})
        self.assertIsNotNone(res.action)
        self.assertEqual(res.action["type"], "map.focus")
        self.assertEqual(res.action["center"], [5.35, -4.02])  # [lat, lng]

    def test_buffer_around_program_returns_circle(self):
        res = executor.run_tool(self.user, "buffer_around_program",
                                {"program_name": "Callisto", "radius_km": 2}, {})
        self.assertEqual(res.action["type"], "map.circle")
        self.assertEqual(res.action["radius_m"], 2000)
        self.assertEqual(res.action["center"], [5.35, -4.02])

    def test_distance_between_programs(self):
        RealEstateProgram.objects.create(
            code="HEL", name="Heliopolis", slug="heliopolis",
            country=self.country, project=self.project,
            centroid=Point(-3.96, 5.30, srid=4326))
        res = executor.run_tool(self.user, "distance_between_programs",
                                {"program_a": "Callisto", "program_b": "Heliopolis"}, {})
        self.assertEqual(res.action["type"], "map.line")
        self.assertEqual(len(res.action["points"]), 2)
        self.assertGreater(res.content["distance_km"], 0)

    def test_set_map_basemap_satellite(self):
        res = executor.run_tool(self.user, "set_map_basemap", {"style": "satellite"}, {})
        self.assertEqual(res.action, {"type": "map.basemap", "basemap": "satellite"})

    def test_set_map_basemap_unknown(self):
        res = executor.run_tool(self.user, "set_map_basemap", {"style": "hologramme"}, {})
        self.assertIn("error", res.content)
        self.assertIsNone(res.action)

    def test_show_orthophoto_none_published(self):
        res = executor.run_tool(self.user, "show_program_orthophoto",
                                {"program_name": "Callisto"}, {})
        self.assertIsNone(res.action)  # pas d'ortho publiée
        self.assertIn("note", res.content)

    def test_show_orthophoto_published(self):
        from parcelaire.models import ProgramOrthophoto
        ProgramOrthophoto.objects.create(
            program=self.program, name="Ortho", reference_year=2026,
            reference_month=3, status="DONE")
        res = executor.run_tool(self.user, "show_program_orthophoto",
                                {"program_name": "Callisto"}, {})
        self.assertEqual(res.action["type"], "map.ortho")
        self.assertEqual(res.action["program_id"], self.program.id)

    def test_customer_search_blocked_without_pii_permission(self):
        res = executor.run_tool(self.user, "search_entities",
                                {"query": "Koné", "kind": "customer"}, {})
        self.assertEqual(res.content["count"], 0)  # pas de recherche nominative sans droit

    def test_customer_search_empty_query_blocked_without_pii(self):
        # Requête vide : ne doit RIEN divulguer (ni IDs ni compte) sans droit PII.
        res = executor.run_tool(self.user, "search_entities", {"kind": "customer"}, {})
        self.assertEqual(res.content["count"], 0)

    def test_customer_search_shows_name_with_pii(self):
        res = executor.run_tool(self.piiuser, "search_entities",
                                {"query": "Koné", "kind": "customer"}, {})
        labels = [r["label"] for r in res.content["results"]]
        self.assertTrue(any("Koné" in lbl for lbl in labels), labels)


class BusinessQueryTests(CopilotBaseTestCase):
    def test_count_parcels_by_status_unknown(self):
        res = executor.run_tool(self.user, "count_parcels_by_status", {"status": "flottant"}, {})
        self.assertIn("error", res.content)

    def test_count_parcels_by_status_normalizes_alias(self):
        res = executor.run_tool(self.user, "count_parcels_by_status", {"status": "disponibles"}, {})
        self.assertEqual(res.content["status"], "AVAILABLE")
        self.assertIn("count", res.content)

    def test_programs_without_orthophoto_lists_callisto(self):
        res = executor.run_tool(self.user, "list_programs_without_orthophoto", {}, {})
        self.assertIn("Callisto", res.content["programs"])

    def test_sales_this_month_count_and_financial_masking(self):
        from django.utils import timezone

        from parcelaire.models import SaleFile
        SaleFile.objects.create(sale_number="V-COP-1", program=self.program,
                                customer=self.customer, agreed_price=1000000,
                                net_price=1000000, sale_date=timezone.now().date())
        res = executor.run_tool(self.user, "sales_this_month", {}, {})
        self.assertGreaterEqual(res.content["count"], 1)
        self.assertEqual(res.content["total_net"], registry.MASKED)  # sans droit financier
        res_fin = executor.run_tool(self.finuser, "sales_this_month", {}, {})
        self.assertNotEqual(res_fin.content["total_net"], registry.MASKED)

    def test_customers_by_payment_ratio_gated_by_financial_permission(self):
        denied = executor.run_tool(self.user, "customers_by_payment_ratio",
                                   {"min_percent": 50}, {})
        self.assertIn("error", denied.content)  # permission refusée (pas de droit financier)
        ok = executor.run_tool(self.finuser, "customers_by_payment_ratio",
                               {"min_percent": 50}, {})
        self.assertIn("count", ok.content)


class SqlAgentTests(CopilotBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Utilisateur habilité SQL mais SANS droit financier/PII.
        cls.sqluser = User.objects.create_user("copilot-sql", password="pwd")
        cls.sqluser.user_permissions.add(
            Permission.objects.get(content_type__app_label="ai_copilot",
                                    codename="use_sql_agent"))
        cls.program_table = RealEstateProgram._meta.db_table

    def test_denied_without_permission(self):
        res = executor.run_tool(self.user, "sql_query",
                                {"sql": f"SELECT id FROM {self.program_table}"}, {})
        self.assertIn("error", res.content)
        self.assertIsNone(res.action)

    def test_select_allowed_table_returns_rows(self):
        res = executor.run_tool(self.sqluser, "sql_query",
                                {"sql": f"SELECT id, name FROM {self.program_table}"}, {})
        self.assertIn("rows", res.content)
        names = [r.get("name") for r in res.content["rows"]]
        self.assertIn("Callisto", names)

    def test_rejects_non_select(self):
        res = executor.run_tool(self.sqluser, "sql_query",
                                {"sql": f"DELETE FROM {self.program_table}"}, {})
        self.assertIn("error", res.content)

    def test_rejects_multiple_statements(self):
        res = executor.run_tool(self.sqluser, "sql_query",
                                {"sql": f"SELECT id FROM {self.program_table}; DROP TABLE x"}, {})
        self.assertIn("error", res.content)

    def test_rejects_sensitive_table_without_perms(self):
        from parcelaire.models import Customer
        res = executor.run_tool(self.sqluser, "sql_query",
                                {"sql": f"SELECT * FROM {Customer._meta.db_table}"}, {})
        self.assertIn("error", res.content)
        self.assertIn("autorisée", res.content["error"])

    def test_rejects_comma_join_bypass(self):
        # Contournement historique : une table interdite jointe par virgule
        # n'était pas capturée par l'extraction FROM/JOIN → doit être refusée.
        res = executor.run_tool(self.sqluser, "sql_query",
                                {"sql": f"SELECT p.id FROM {self.program_table} p, auth_user u"}, {})
        self.assertIn("error", res.content)
        self.assertIn("auth_user", res.content["error"])

    def test_rejects_auth_user_in_subquery(self):
        res = executor.run_tool(self.sqluser, "sql_query",
                                {"sql": "SELECT (SELECT password FROM auth_user LIMIT 1)"}, {})
        self.assertIn("error", res.content)


class ReportingTests(CopilotBaseTestCase):
    def test_analytics_digest_masks_finance(self):
        res = executor.run_tool(self.user, "get_analytics_digest", {}, {})
        self.assertIn("kpis", res.content)
        self.assertEqual(res.content["kpis"]["ca_potentiel"], "Masqué")

    def test_analytics_digest_masks_client_pii_without_permission(self):
        from django.utils import timezone

        from parcelaire.models import Parcel, ParcelDataset, SaleFile
        ds = ParcelDataset.objects.create(name="DS", program=self.program)
        parcel = Parcel.objects.create(dataset=ds, program=self.program, lot_number="L1")
        SaleFile.objects.create(sale_number="V-PII-1", program=self.program,
                                customer=self.customer, parcel=parcel,
                                agreed_price=1000000, net_price=1000000,
                                sales_agent="Jean Commercial",
                                sale_date=timezone.now().date())
        # Sans droit PII : aucun nom de client/commercial ne doit fuiter vers le LLM.
        res = executor.run_tool(self.user, "get_analytics_digest", {}, {})
        for r in res.content["clients_at_risk"]:
            self.assertNotIn("Koné", str(r.get("customer")))
            self.assertNotEqual(r.get("sales_agent"), "Jean Commercial")
        # Avec droit PII : le nom réel est présent.
        res_pii = executor.run_tool(self.piiuser, "get_analytics_digest", {}, {})
        names = [r.get("customer") for r in res_pii.content["clients_at_risk"]]
        self.assertTrue(any("Koné" in str(n) for n in names), names)

    def test_generate_report_dashboard_pdf(self):
        res = executor.run_tool(self.user, "generate_report", {"kind": "dashboard"}, {})
        self.assertEqual(res.action["type"], "download")
        self.assertTrue(res.action["url"].endswith("/dashboard/report/"))

    def test_generate_report_risques_xlsx(self):
        res = executor.run_tool(self.user, "generate_report", {"kind": "risques"}, {})
        self.assertIn("fmt=xlsx", res.action["url"])
        self.assertTrue(res.action["filename"].endswith(".xlsx"))

    def test_generate_report_risques_word(self):
        res = executor.run_tool(self.user, "generate_report",
                                {"kind": "risques", "format": "word"}, {})
        self.assertIn("fmt=docx", res.action["url"])
        self.assertTrue(res.action["filename"].endswith(".docx"))

    def test_generate_report_unknown(self):
        res = executor.run_tool(self.user, "generate_report", {"kind": "martien"}, {})
        self.assertIn("error", res.content)

    def test_at_risk_xlsx_endpoint(self):
        self.client.force_login(self.user)
        r = self.client.get("/api/analytics/at-risk/export/?fmt=xlsx")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])

    def test_at_risk_docx_endpoint(self):
        self.client.force_login(self.user)
        r = self.client.get("/api/analytics/at-risk/export/?fmt=docx")
        self.assertEqual(r.status_code, 200)
        self.assertIn("wordprocessingml", r["Content-Type"])


class UrbanismTests(CopilotBaseTestCase):
    def _geo(self, lat, lng):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = [{"lat": str(lat), "lon": str(lng),
                                   "display_name": "Point test"}]
        return fake

    def test_programs_near_place_lists_within_radius(self):
        with mock.patch("requests.get", return_value=self._geo(5.351, -4.021)):
            res = executor.run_tool(self.user, "programs_near_place",
                                    {"place": "CHU de Cocody", "radius_km": 5}, {})
        self.assertEqual(res.action["type"], "map.circle")
        self.assertEqual(res.action["radius_m"], 5000)
        names = [p["program"] for p in res.content["programs"]]
        self.assertIn("Callisto", names)

    def test_programs_near_place_excludes_far(self):
        with mock.patch("requests.get", return_value=self._geo(9.0, -5.0)):
            res = executor.run_tool(self.user, "programs_near_place",
                                    {"place": "très loin", "radius_km": 1}, {})
        self.assertEqual(res.content["count"], 0)

    def test_programs_near_place_geocode_error(self):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = []
        with mock.patch("requests.get", return_value=fake):
            res = executor.run_tool(self.user, "programs_near_place", {"place": "zzz"}, {})
        self.assertIn("error", res.content)
        self.assertIsNone(res.action)


class ParcelProximityTests(CopilotBaseTestCase):
    def _geo(self, lat, lng):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = [{"lat": str(lat), "lon": str(lng), "display_name": "Point"}]
        return fake

    @staticmethod
    def _square(lng0, lat0, d=0.0002):
        from django.contrib.gis.geos import MultiPolygon, Polygon
        ring = ((lng0 - d, lat0 - d), (lng0 + d, lat0 - d), (lng0 + d, lat0 + d),
                (lng0 - d, lat0 + d), (lng0 - d, lat0 - d))
        return MultiPolygon(Polygon(ring), srid=4326)

    def test_parcels_near_place_uses_metric_postgis(self):
        from parcelaire.models import Parcel, ParcelDataset
        ds = ParcelDataset.objects.create(name="DS", program=self.program)
        Parcel.objects.create(dataset=ds, program=self.program, lot_number="NEAR",
                              geometry=self._square(-4.0005, 5.3505))   # ~80 m du point
        Parcel.objects.create(dataset=ds, program=self.program, lot_number="FAR",
                              geometry=self._square(-4.5, 5.5))          # ~70 km
        with mock.patch("requests.get", return_value=self._geo(5.35, -4.00)):
            res = executor.run_tool(self.user, "parcels_near_place",
                                    {"place": "centre", "radius_km": 1}, {})
        lots = [p["lot"] for p in res.content["parcels"]]
        self.assertIn("NEAR", lots)         # ~80 m ≤ 1 km
        self.assertNotIn("FAR", lots)       # ~70 km exclu (⇒ mètres, pas degrés)
        self.assertEqual(res.action["type"], "map.circle")
        near = next(p for p in res.content["parcels"] if p["lot"] == "NEAR")
        self.assertLess(near["distance_m"], 1000)


class GeoToolsTests(CopilotBaseTestCase):
    def _geo(self, lat, lng):
        fake = mock.Mock(status_code=200)
        fake.json.return_value = [{"lat": str(lat), "lon": str(lng), "display_name": "Lieu"}]
        return fake

    @staticmethod
    def _square(lng0, lat0, d=0.0002):
        from django.contrib.gis.geos import MultiPolygon, Polygon
        ring = ((lng0 - d, lat0 - d), (lng0 + d, lat0 - d), (lng0 + d, lat0 + d),
                (lng0 - d, lat0 + d), (lng0 - d, lat0 - d))
        return MultiPolygon(Polygon(ring), srid=4326)

    def setUp(self):
        from parcelaire.models import Parcel, ParcelDataset, RealEstateProgram
        # Programme SANS centroïde, mais dont les parcelles SONT géolocalisées
        # (cas réel de « Callisto » qui faisait échouer programs_near_place).
        self.prog_nogeo = RealEstateProgram.objects.create(
            code="NOGEO", name="SansCentroide", slug="sanscentroide",
            country=self.country, project=self.project)
        # Le dataset doit appartenir AU MÊME programme que ses parcelles.
        self.ds = ParcelDataset.objects.create(name="DS", program=self.prog_nogeo)
        Parcel.objects.create(dataset=self.ds, program=self.prog_nogeo,
                              lot_number="34", geometry=self._square(-4.0005, 5.3505))
        Parcel.objects.create(dataset=self.ds, program=self.prog_nogeo,
                              lot_number="49", geometry=self._square(-4.0100, 5.3600))

    def test_programs_near_place_finds_program_via_its_parcels(self):
        # Bug corrigé : le programme n'a pas de centroïde mais ses parcelles sont
        # dans le rayon → il doit être trouvé (source de vérité = parcelles).
        with mock.patch("requests.get", return_value=self._geo(5.35, -4.00)):
            res = executor.run_tool(self.user, "programs_near_place",
                                    {"place": "aéroport", "radius_km": 5}, {})
        names = [p["program"] for p in res.content["programs"]]
        self.assertIn("SansCentroide", names)

    def test_count_parcels_in_program(self):
        res = executor.run_tool(self.user, "count_parcels_in_program",
                                {"program": "SansCentroide"}, {})
        self.assertEqual(res.content["total_parcels"], 2)
        self.assertEqual(res.content["with_geometry"], 2)

    def test_distance_between_parcels_draws_line(self):
        res = executor.run_tool(self.user, "distance_between_parcels",
                                {"program": "SansCentroide", "lot_a": "34", "lot_b": "49"}, {})
        self.assertEqual(res.action["type"], "map.line")
        self.assertEqual(len(res.action["points"]), 2)
        self.assertGreater(res.content["distance_m"], 0)

    def test_distance_between_parcels_unknown_lot(self):
        res = executor.run_tool(self.user, "distance_between_parcels",
                                {"program": "SansCentroide", "lot_a": "34", "lot_b": "999"}, {})
        self.assertIn("error", res.content)

    def test_distance_to_place_draws_line(self):
        with mock.patch("requests.get", return_value=self._geo(5.35, -4.00)):
            res = executor.run_tool(self.user, "distance_to_place",
                                    {"program": "SansCentroide", "place": "aéroport"}, {})
        self.assertEqual(res.action["type"], "map.line")
        self.assertEqual(res.content["nearest_lot"], "34")  # la plus proche
        self.assertGreater(res.content["distance_m"], 0)


class SideEffectActionTests(CopilotBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from parcelaire.models import ProgramOrthophoto
        cls.orthouser = User.objects.create_user("copilot-ortho", password="pwd")
        cls.orthouser.user_permissions.add(Permission.objects.get(
            content_type__app_label="parcelaire", codename="change_programorthophoto"))
        cls.ortho = ProgramOrthophoto.objects.create(
            program=cls.program, name="Ortho KO", reference_year=2026,
            reference_month=3, status="FAILED")

    def test_retry_denied_without_permission(self):
        res = executor.run_tool(self.user, "retry_orthophoto_processing",
                                {"orthophoto_id": self.ortho.id}, {})
        self.assertIn("error", res.content)
        self.assertTrue(CopilotToolCall.objects.filter(
            tool_name="retry_orthophoto_processing", status="denied").exists())

    def test_retry_requires_confirmation(self):
        res = executor.run_tool(self.orthouser, "retry_orthophoto_processing",
                                {"orthophoto_id": self.ortho.id}, {})
        self.assertEqual(res.action["type"], "confirm")
        self.assertEqual(res.action["tool"], "retry_orthophoto_processing")
        self.assertTrue(res.action.get("token"))          # jeton signé émis
        self.assertIn("Callisto", res.action["summary"])  # résumé lisible (nom programme)
        self.ortho.refresh_from_db()
        self.assertEqual(self.ortho.status, "FAILED")  # aucun effet sans confirmation
        self.assertTrue(CopilotToolCall.objects.filter(
            tool_name="retry_orthophoto_processing", status="needs_confirmation").exists())

    def test_retry_executes_after_confirmation(self):
        with mock.patch("parcelaire.tasks.process_orthophoto.delay") as delay:
            res = executor.run_tool(self.orthouser, "retry_orthophoto_processing",
                                    {"orthophoto_id": self.ortho.id}, {},
                                    allow_side_effects=True)
        self.assertTrue(res.content["celery_queued"])
        delay.assert_called_once_with(self.ortho.id)
        self.ortho.refresh_from_db()
        self.assertEqual(self.ortho.status, "PENDING")
        self.assertTrue(CopilotToolCall.objects.filter(  # audit : statut dédié
            tool_name="retry_orthophoto_processing", status="confirmed").exists())

    def test_confirm_path_via_agent(self):
        from ai_copilot.agent import run_confirmed
        conv = CopilotConversation.objects.create(user=self.orthouser, title="t")
        with mock.patch("parcelaire.tasks.process_orthophoto.delay"):
            out = run_confirmed(self.orthouser, "retry_orthophoto_processing",
                                {"orthophoto_id": self.ortho.id}, {}, conv)
        self.assertIn("relancé", out["reply"])
        self.assertEqual(out["actions"][0]["type"], "navigate")

    def test_confirm_rejects_non_side_effecting_tool(self):
        from ai_copilot.agent import run_confirmed
        conv = CopilotConversation.objects.create(user=self.user, title="t")
        out = run_confirmed(self.user, "get_dashboard_summary", {}, {}, conv)
        self.assertIn("confirmable", out["reply"])

    def _proposal_token(self, user=None):
        res = executor.run_tool(user or self.orthouser, "retry_orthophoto_processing",
                                {"orthophoto_id": self.ortho.id}, {})
        return res.action["token"]

    def test_view_confirm_action_executes_without_llm(self):
        # Le chemin de confirmation ne passe PAS par le LLM (pas de clé requise),
        # mais exige le jeton signé émis lors de la proposition.
        token = self._proposal_token()
        self.client.force_login(self.orthouser)
        with mock.patch("parcelaire.tasks.process_orthophoto.delay"):
            r = self.client.post("/api/copilot/chat/",
                                 {"confirm_action": {"token": token}},
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("relancé", r.json()["reply"])

    def test_view_confirm_rejects_forged_token(self):
        self.client.force_login(self.orthouser)
        r = self.client.post("/api/copilot/chat/",
                             {"confirm_action": {"token": "forged.invalid.token"}},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_confirm_token_bound_to_issuing_user(self):
        # Un jeton émis pour un utilisateur ne peut pas être rejoué par un autre,
        # même détenteur de la permission.
        token = self._proposal_token(self.orthouser)
        other = User.objects.create_user("copilot-ortho2", password="pwd")
        other.user_permissions.add(Permission.objects.get(
            content_type__app_label="parcelaire", codename="change_programorthophoto"))
        self.client.force_login(other)
        r = self.client.post("/api/copilot/chat/",
                             {"confirm_action": {"token": token}},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_view_confirm_without_token_is_not_a_confirmation(self):
        # Sans jeton : ce n'est pas une confirmation → retombe sur le chemin
        # message, qui exige la clé LLM (503 ici) — donc aucun effet de bord.
        self.client.force_login(self.orthouser)
        with mock.patch("parcelaire.tasks.process_orthophoto.delay") as delay:
            r = self.client.post(
                "/api/copilot/chat/",
                {"confirm_action": {"tool": "retry_orthophoto_processing",
                                    "arguments": {"orthophoto_id": self.ortho.id}}},
                content_type="application/json")
        self.assertEqual(r.status_code, 503)
        delay.assert_not_called()


class AgentLoopTests(CopilotBaseTestCase):
    @override_settings(DEEPSEEK_API_KEY="test-key")
    def test_tool_call_then_final_answer(self):
        conv = CopilotConversation.objects.create(user=self.user, title="t")
        responses = [
            {"choices": [{"message": {"content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {
                    "name": "focus_map_on_program",
                    "arguments": json.dumps({"program_name": "Callisto"})}}]}}]},
            {"choices": [{"message": {"content": "Carte centrée sur Callisto."}}]},
        ]
        with mock.patch("ai_copilot.gateway.chat_completion", side_effect=responses):
            out = run_turn(self.user, "Va sur Callisto", {"route": "/carte"}, conv)
        self.assertEqual(out["reply"], "Carte centrée sur Callisto.")
        self.assertTrue(any(a["type"] == "map.focus" for a in out["actions"]))
        # historique persisté : message user + assistant
        self.assertTrue(conv.messages.filter(role="user").exists())
        self.assertTrue(conv.messages.filter(role="assistant").exists())
        self.assertTrue(CopilotToolCall.objects.filter(
            tool_name="focus_map_on_program", status="ok").exists())


@override_settings(COPILOT_PROVIDER_PRIORITY=["deepseek", "openai", "anthropic"])
class GatewayRoutingTests(TestCase):
    @override_settings(DEEPSEEK_API_KEY="", OPENAI_API_KEY="", ANTHROPIC_API_KEY="")
    def test_no_provider_means_not_configured(self):
        self.assertFalse(gateway.is_configured())
        self.assertEqual(gateway.available_engines(), [])

    @override_settings(DEEPSEEK_API_KEY="", OPENAI_API_KEY="k", ANTHROPIC_API_KEY="k")
    def test_auto_resolves_first_configured_by_priority(self):
        self.assertEqual(gateway._resolve("auto"), "openai")

    @override_settings(DEEPSEEK_API_KEY="k", OPENAI_API_KEY="k", ANTHROPIC_API_KEY="")
    def test_engines_prepend_auto_when_multiple(self):
        vals = [e["value"] for e in gateway.available_engines()]
        self.assertEqual(vals[0], "auto")
        self.assertIn("openai", vals)
        self.assertNotIn("anthropic", vals)  # non configuré → absent

    @override_settings(DEEPSEEK_API_KEY="k", OPENAI_API_KEY="", ANTHROPIC_API_KEY="")
    def test_selecting_unconfigured_engine_errors(self):
        with self.assertRaises(gateway.GatewayError):
            gateway.chat_completion([{"role": "user", "content": "hi"}], None, model="claude")

    @override_settings(DEEPSEEK_API_KEY="k")
    def test_openai_compatible_hits_chat_completions(self):
        canned = {"choices": [{"message": {"content": "ok"}}]}
        fake = mock.Mock(status_code=200)
        fake.json.return_value = canned
        with mock.patch("requests.post", return_value=fake) as post:
            out = gateway.chat_completion([{"role": "user", "content": "hi"}],
                                          None, model="deepseek")
        self.assertEqual(out, canned)
        self.assertIn("/chat/completions", post.call_args[0][0])

    @override_settings(DEEPSEEK_API_KEY="", OPENAI_API_KEY="", ANTHROPIC_API_KEY="k")
    def test_anthropic_translated_to_openai_shape(self):
        anthropic_resp = {"content": [
            {"type": "text", "text": "Je regarde."},
            {"type": "tool_use", "id": "tu_1", "name": "focus_map_on_program",
             "input": {"program_name": "Callisto"}},
        ]}
        fake = mock.Mock(status_code=200)
        fake.json.return_value = anthropic_resp
        msgs = [{"role": "system", "content": "sys"},
                {"role": "user", "content": "va sur Callisto"}]
        tools = [{"type": "function", "function": {
            "name": "focus_map_on_program", "description": "d",
            "parameters": {"type": "object", "properties": {}}}}]
        with mock.patch("requests.post", return_value=fake) as post:
            out = gateway.chat_completion(msgs, tools, model="claude")
        msg = out["choices"][0]["message"]
        self.assertEqual(msg["content"], "Je regarde.")
        self.assertEqual(msg["tool_calls"][0]["function"]["name"], "focus_map_on_program")
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["system"], "sys")
        self.assertEqual(sent["tools"][0]["name"], "focus_map_on_program")
        self.assertIn("input_schema", sent["tools"][0])
        self.assertTrue(post.call_args[0][0].endswith("/v1/messages"))

    def test_to_anthropic_maps_tool_call_and_result(self):
        msgs = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "foo", "arguments": '{"x": 1}'}}]},
            {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'},
        ]
        _system, conv, _tools = gateway._to_anthropic(msgs, None)
        self.assertEqual(conv[0]["role"], "assistant")
        self.assertEqual(conv[0]["content"][0]["type"], "tool_use")
        self.assertEqual(conv[0]["content"][0]["input"], {"x": 1})
        self.assertEqual(conv[1]["content"][0]["type"], "tool_result")
        self.assertEqual(conv[1]["content"][0]["tool_use_id"], "c1")


class CopilotEnginesViewTests(CopilotBaseTestCase):
    @override_settings(DEEPSEEK_API_KEY="k", OPENAI_API_KEY="k", ANTHROPIC_API_KEY="")
    def test_engines_endpoint_lists_configured(self):
        self.client.force_login(self.user)
        r = self.client.get("/api/copilot/engines/")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["configured"])
        vals = [e["value"] for e in body["engines"]]
        self.assertIn("auto", vals)
        self.assertIn("openai", vals)

    def test_engines_endpoint_requires_auth(self):
        self.assertEqual(self.client.get("/api/copilot/engines/").status_code, 403)


class CopilotViewTests(CopilotBaseTestCase):
    def test_requires_authentication(self):
        self.assertEqual(self.client.post("/api/copilot/chat/",
                         {"message": "salut"}, content_type="application/json").status_code, 403)

    def test_503_when_not_configured(self):
        self.client.force_login(self.user)  # pas de DEEPSEEK_API_KEY
        r = self.client.post("/api/copilot/chat/", {"message": "salut"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 503)

    @override_settings(DEEPSEEK_API_KEY="test-key")
    def test_chat_ok_with_mocked_llm(self):
        self.client.force_login(self.user)
        canned = {"choices": [{"message": {"content": "Bonjour, comment puis-je aider ?"}}]}
        with mock.patch("ai_copilot.gateway.chat_completion", return_value=canned):
            r = self.client.post("/api/copilot/chat/",
                                 {"message": "Bonjour", "context": {"route": "/"}},
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["reply"], "Bonjour, comment puis-je aider ?")
        self.assertIn("conversation_id", body)

    @override_settings(DEEPSEEK_API_KEY="test-key")
    def test_empty_message_rejected(self):
        self.client.force_login(self.user)
        r = self.client.post("/api/copilot/chat/", {"message": "   "},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)


class ConversationHistoryTests(CopilotBaseTestCase):
    def test_lists_only_own_conversations(self):
        from ai_copilot.models import CopilotMessage
        mine = CopilotConversation.objects.create(user=self.user, title="Ma conv")
        CopilotMessage.objects.create(conversation=mine, role="user", content="salut")
        CopilotConversation.objects.create(user=self.finuser, title="Autre")  # d'un autre user
        self.client.force_login(self.user)
        r = self.client.get("/api/copilot/conversations/")
        self.assertEqual(r.status_code, 200)
        titles = [c["title"] for c in r.json()["conversations"]]
        self.assertIn("Ma conv", titles)
        self.assertNotIn("Autre", titles)

    def test_detail_returns_messages_for_owner(self):
        from ai_copilot.models import CopilotMessage
        conv = CopilotConversation.objects.create(user=self.user, title="C")
        CopilotMessage.objects.create(conversation=conv, role="user", content="Q ?")
        CopilotMessage.objects.create(conversation=conv, role="assistant", content="R.")
        CopilotMessage.objects.create(conversation=conv, role="tool", content="",
                                      metadata={"tool": "x"})
        self.client.force_login(self.user)
        r = self.client.get(f"/api/copilot/conversations/{conv.id}/")
        self.assertEqual(r.status_code, 200)
        roles = [m["role"] for m in r.json()["messages"]]
        self.assertEqual(roles, ["user", "assistant"])  # lignes 'tool' exclues

    def test_detail_404_for_other_users_conversation(self):
        conv = CopilotConversation.objects.create(user=self.finuser, title="Privé")
        self.client.force_login(self.user)
        r = self.client.get(f"/api/copilot/conversations/{conv.id}/")
        self.assertEqual(r.status_code, 404)

    def test_history_requires_authentication(self):
        self.assertEqual(self.client.get("/api/copilot/conversations/").status_code, 403)
