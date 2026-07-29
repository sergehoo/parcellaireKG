import json
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings

from ai_copilot import executor
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
                         "focus_map_on_program", "generate_dashboard_report"} <= names)


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
