"""Tests Phase 4 : contexte de rapport, rendu PDF (WeasyPrint), envoi e-mail."""
from datetime import date

from django.core import mail
from django.test import TestCase

from alerting.models import ConstructionProgressSnapshot, PaymentSnapshot
from alerting.services import email_sender, pdf_renderer, report_builder


class ReportFixture(TestCase):
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
        cls.ref = date(2026, 7, 20)
        # un instantané antérieur pour exercer les variations
        ConstructionProgressSnapshot.objects.create(program=cls.program, recorded_at=date(2026, 7, 13),
                                                    progress_percent=26)
        PaymentSnapshot.objects.create(program=cls.program, recorded_at=date(2026, 7, 13), payment_rate=66)

    def ctx(self):
        return report_builder.build_report_context(
            reference_date=self.ref, window_days=7, generated_at="2026-07-20 08:00", can_fin=True)


class ReportBuilderTests(ReportFixture):
    def test_context_shape(self):
        c = self.ctx()
        self.assertEqual(c["summary"]["programs_count"], 1)
        self.assertEqual(c["programs"][0]["construction"]["variation_points"], 2.0)  # 28 - 26
        self.assertEqual(c["programs"][0]["payment"]["variation_points"], 4.0)       # 70 - 66
        # le client en écart apparaît en prioritaire
        self.assertTrue(c["priority_clients"])
        self.assertEqual(c["priority_clients"][0]["lot"], "18")
        self.assertTrue(c["charts"]["payment_vs_construction"].startswith("<svg"))
        self.assertTrue(c["recommendations"])


class PdfRenderTests(ReportFixture):
    def test_pdf_renders(self):
        pdf = pdf_renderer.render_report_pdf(self.ctx())
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 2000)

    def test_filename(self):
        name = pdf_renderer.report_filename(self.ctx())
        self.assertTrue(name.endswith(".pdf"))
        self.assertIn("kotibe", name)


class EmailTests(ReportFixture):
    def test_send_with_attachment(self):
        c = self.ctx()
        pdf = pdf_renderer.render_report_pdf(c)
        sent = email_sender.send_report_email(
            c, pdf_bytes=pdf, pdf_filename="rapport.pdf",
            recipients=["dg@kaydan.tech", "tech@kaydan.tech"])
        self.assertEqual(sent, 2)
        self.assertEqual(len(mail.outbox), 2)
        msg = mail.outbox[0]
        self.assertIn("ALERTE PARCELLAIRE", msg.subject)
        self.assertIn("Kotibe", msg.subject)
        self.assertEqual(len(msg.attachments), 1)
        self.assertEqual(msg.attachments[0][0], "rapport.pdf")
        self.assertEqual(msg.attachments[0][2], "application/pdf")
        # corps HTML présent
        self.assertTrue(any("text/html" in a[1] for a in msg.alternatives))

    def test_no_recipients_no_send(self):
        self.assertEqual(email_sender.send_report_email(self.ctx(), recipients=[]), 0)
        self.assertEqual(len(mail.outbox), 0)
