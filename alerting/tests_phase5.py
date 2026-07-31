"""Tests Phase 5 : orchestration Celery (dispatch complet, échéances, retry, cleanup)."""
import os
import tempfile
from datetime import date, timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from alerting import tasks
from alerting.models import (
    AlertConfiguration, AlertDetection, AlertDispatch, AlertRecipient,
    AlertRecipientGroup, AlertReport, DispatchStatus, Frequency, Retention, Severity,
)
from alerting.services import dispatch_service

TMP_MEDIA = tempfile.mkdtemp(prefix="alert-media-")


class DispatchFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        from parcelaire.models import (
            ConstructionProject, Country, Customer, Parcel, ParcelDataset,
            Payment, ProjetImmobilier, RealEstateProgram, SaleFile,
        )
        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(code="KOT", nom="Kaydan", country=cls.country)
        cls.program = RealEstateProgram.objects.create(
            code="KOTIBE", name="Kotibe", slug="kotibe", country=cls.country, project=cls.project)
        cls.ds = ParcelDataset.objects.create(name="DS", program=cls.program)
        cust = Customer.objects.create(customer_type="INDIVIDUAL", last_name="Koné")
        a = Parcel.objects.create(program=cls.program, dataset=cls.ds, lot_number="18")
        ConstructionProject.objects.create(parcel=a, code="CA", title="C", progress_percent=28)
        sf = SaleFile.objects.create(sale_number="A", program=cls.program, customer=cust, parcel=a,
                                     agreed_price=100_000_000, net_price=100_000_000)
        Payment.objects.create(payment_number="PA", sale_file=sf, amount=70_000_000,
                               status="CONFIRMED", payment_method="BANK", payment_date=date(2026, 7, 10))

        cls.r1 = AlertRecipient.objects.create(email="dg@kaydan.tech", last_name="DG")
        cls.r2 = AlertRecipient.objects.create(email="tech@kaydan.tech", last_name="Tech")
        cls.group = AlertRecipientGroup.objects.create(name="Direction technique")
        cls.group.recipients.add(cls.r2)

    def make_config(self, **kwargs):
        defaults = dict(name="Hebdo DG", frequency=Frequency.WEEKLY, day_of_week=0,
                        include_pdf=True, minimum_severity=Severity.INFORMATION)
        defaults.update(kwargs)
        cfg = AlertConfiguration.objects.create(**defaults)
        cfg.recipients.add(self.r1)
        cfg.recipient_groups.add(self.group)
        return cfg


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class RunConfigurationTests(DispatchFixture):
    def test_end_to_end_dispatch(self):
        cfg = self.make_config()
        d = dispatch_service.run_configuration(cfg, reference_date=date(2026, 7, 20))
        self.assertEqual(d.status, DispatchStatus.SENT)
        self.assertEqual(d.email_count, 2)                 # r1 + membre du groupe
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(d.deliveries.count(), 2)
        # PDF archivé sur disque + rapport lié.
        self.assertIsNotNone(d.report)
        self.assertTrue(os.path.exists(os.path.join(TMP_MEDIA, d.report.file_path)))
        self.assertTrue(d.checksum)
        # Détections persistées pour la période.
        self.assertGreaterEqual(AlertDetection.objects.count(), 1)
        # Prochaine échéance recalculée (lundi).
        cfg.refresh_from_db()
        self.assertIsNotNone(cfg.next_send_at)
        self.assertEqual(cfg.next_send_at.weekday(), 0)
        self.assertIsNotNone(cfg.last_sent_at)

    def test_preview_generates_without_sending(self):
        cfg = self.make_config()
        d = dispatch_service.run_configuration(cfg, reference_date=date(2026, 7, 20), preview=True)
        self.assertEqual(d.status, DispatchStatus.READY)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(d.is_preview)

    def test_no_recipients_marks_failed(self):
        cfg = AlertConfiguration.objects.create(name="Sans dest.", frequency=Frequency.WEEKLY)
        d = dispatch_service.run_configuration(cfg, reference_date=date(2026, 7, 20))
        self.assertEqual(d.status, DispatchStatus.FAILED)
        self.assertIn("destinataire", d.error_message)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class ScheduleTests(DispatchFixture):
    def test_due_configurations(self):
        past = self.make_config(name="Échue")
        past.next_send_at = timezone.now() - timedelta(hours=1)
        past.save(update_fields=["next_send_at"])
        future = self.make_config(name="Future")
        future.next_send_at = timezone.now() + timedelta(days=1)
        future.save(update_fields=["next_send_at"])
        manual = self.make_config(name="Manuel", frequency=Frequency.MANUAL)
        manual.next_send_at = timezone.now() - timedelta(hours=1)
        manual.save(update_fields=["next_send_at"])

        due_ids = {c.id for c in dispatch_service.due_configurations()}
        self.assertIn(past.id, due_ids)
        self.assertNotIn(future.id, due_ids)
        self.assertNotIn(manual.id, due_ids)  # MANUEL exclu

    def test_evaluate_task_processes_due(self):
        cfg = self.make_config(name="Échue")
        cfg.next_send_at = timezone.now() - timedelta(hours=1)
        cfg.save(update_fields=["next_send_at"])
        res = tasks.evaluate_alert_configurations()
        self.assertIn(cfg.id, res["processed"])
        self.assertEqual(AlertDispatch.objects.filter(configuration=cfg,
                                                      status=DispatchStatus.SENT).count(), 1)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class CleanupTests(DispatchFixture):
    def test_cleanup_removes_expired_files(self):
        os.makedirs(TMP_MEDIA, exist_ok=True)
        rel = "alert_reports/test.pdf"
        with open(os.path.join(TMP_MEDIA, "test.pdf"), "wb") as fh:
            fh.write(b"%PDF-1.4 test")
        rel = "test.pdf"
        rep = AlertReport.objects.create(title="Vieux", file_path=rel, retention_days=Retention.D30)
        # created_at est auto_now_add → on le force dans le passé.
        AlertReport.objects.filter(pk=rep.pk).update(created_at=timezone.now() - timedelta(days=40))
        res = tasks.cleanup_old_generated_reports()
        self.assertEqual(res["removed"], 1)
        rep.refresh_from_db()
        self.assertIsNone(rep.file_path)
        self.assertFalse(os.path.exists(os.path.join(TMP_MEDIA, "test.pdf")))
