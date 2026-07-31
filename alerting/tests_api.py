"""Tests Phase 6a : API REST du module d'alertes."""
import tempfile
from datetime import date

from django.contrib.auth.models import Permission, User
from django.core import mail
from django.test import TestCase, override_settings

from alerting.models import (
    AlertConfiguration, AlertDetection, AlertRecipient, Frequency, Severity,
)

TMP_MEDIA = tempfile.mkdtemp(prefix="alert-api-media-")


def perm(codename, app="alerting"):
    return Permission.objects.get(content_type__app_label=app, codename=codename)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class AlertsAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from parcelaire.models import (
            ConstructionProject, Country, Customer, Parcel, ParcelDataset,
            Payment, ProjetImmobilier, RealEstateProgram, SaleFile,
        )
        cls.reader = User.objects.create_user("al-reader", password="pwd")  # authentifié nu
        cls.admin = User.objects.create_superuser("al-admin", "a@a.co", "pwd")
        cls.staff = User.objects.create_user("al-staff", password="pwd")
        cls.staff.user_permissions.add(
            perm("add_alertconfiguration"), perm("change_alertconfiguration"),
            perm("add_alertrecipient"), perm("generate_alertreport"),
            perm("download_alertreport"), perm("acknowledge_alert"),
            perm("view_financial_data", app="parcelaire"),
            perm("view_patient_data", app="parcelaire"))

        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(code="KOT", nom="Kaydan", country=cls.country)
        cls.program = RealEstateProgram.objects.create(
            code="KOTIBE", name="Kotibe", slug="kotibe", country=cls.country, project=cls.project)
        ds = ParcelDataset.objects.create(name="DS", program=cls.program)
        a = Parcel.objects.create(program=cls.program, dataset=ds, lot_number="18")
        ConstructionProject.objects.create(parcel=a, code="CA", title="C", progress_percent=28)
        cust = Customer.objects.create(customer_type="INDIVIDUAL", last_name="Koné")
        sf = SaleFile.objects.create(sale_number="A", program=cls.program, customer=cust, parcel=a,
                                     agreed_price=100_000_000, net_price=100_000_000)
        Payment.objects.create(payment_number="PA", sale_file=sf, amount=70_000_000,
                               status="CONFIRMED", payment_method="BANK", payment_date=date(2026, 7, 10))

    # --- auth ---
    def test_dashboard_requires_auth(self):
        self.assertEqual(self.client.get("/api/alerts/dashboard/").status_code, 403)

    def test_dashboard_kpis(self):
        self.client.force_login(self.admin)
        d = self.client.get("/api/alerts/dashboard/").json()
        for k in ("active_alerts", "active_recipients", "monitored_programs",
                  "reports_this_month", "failed_dispatches", "email_service_ok"):
            self.assertIn(k, d)

    # --- CRUD config ---
    def test_configuration_crud_requires_perm(self):
        self.client.force_login(self.reader)
        r = self.client.post("/api/alerts/configurations/",
                             {"name": "X", "frequency": Frequency.WEEKLY}, "application/json")
        self.assertEqual(r.status_code, 403)  # pas de add_alertconfiguration
        self.client.force_login(self.staff)
        r = self.client.post("/api/alerts/configurations/",
                             {"name": "Hebdo DG", "frequency": Frequency.WEEKLY, "day_of_week": 0},
                             "application/json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNotNone(r.json()["next_send_at"])  # planifié à la création
        self.assertEqual(r.json()["created_by"], self.staff.id)

    # --- recipients ---
    def test_recipient_create(self):
        self.client.force_login(self.staff)
        r = self.client.post("/api/alerts/recipients/",
                             {"email": "dg@kaydan.tech", "last_name": "DG"}, "application/json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(AlertRecipient.objects.filter(email="dg@kaydan.tech").exists())

    # --- generate (preview) + download ---
    def test_generate_preview_and_download(self):
        self.client.force_login(self.staff)
        r = self.client.post("/api/alerts/reports/generate/",
                             {"preview": True, "period_days": 7}, "application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "READY")
        self.assertEqual(len(mail.outbox), 0)               # aperçu : pas d'envoi
        report_id = body["report"]["id"]
        dl = self.client.get(f"/api/alerts/reports/{report_id}/download/")
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl["Content-Type"], "application/pdf")

    def test_generate_requires_permission(self):
        self.client.force_login(self.reader)
        r = self.client.post("/api/alerts/reports/generate/", {"preview": True}, "application/json")
        self.assertEqual(r.status_code, 403)

    # --- detections + acknowledge + masquage ---
    def test_detection_masking_and_acknowledge(self):
        det = AlertDetection.objects.create(
            alert_type="PAYMENT_GT_CONSTRUCTION", severity=Severity.CRITICAL,
            program=self.program, title="Écart +42 — lot 18",
            message="Koné : paiement 70% vs construction 28%.",
            financial_exposure=70_000_000, metadata={"customer": "Koné", "lot": "18"})
        # lecteur nu : montant + message masqués
        self.client.force_login(self.reader)
        row = self.client.get("/api/alerts/detections/").json()["results"][0]
        self.assertIsNone(row["financial_exposure"])
        self.assertIsNone(row["message"])
        self.assertEqual(row["metadata"], {})
        # habilité : visible
        self.client.force_login(self.staff)
        row = self.client.get("/api/alerts/detections/").json()["results"][0]
        self.assertIsNotNone(row["financial_exposure"])
        self.assertIn("Koné", row["message"])
        # acquittement
        ack = self.client.post(f"/api/alerts/detections/{det.id}/acknowledge/")
        self.assertEqual(ack.status_code, 200)
        det.refresh_from_db()
        self.assertEqual(det.status, AlertDetection.Status.ACKNOWLEDGED)
        self.assertEqual(det.acknowledged_by, self.staff)

    # --- SMTP test ---
    def test_smtp_test_sends(self):
        u = User.objects.create_user("al-mgr", password="pwd")
        u.user_permissions.add(perm("manage_alertrecipient"))
        self.client.force_login(u)
        r = self.client.post("/api/alerts/smtp/test/", {"email": "test@kaydan.tech"}, "application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
