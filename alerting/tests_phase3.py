"""Tests Phase 3 : moteur de détection + recommandations."""
from datetime import date

from django.test import TestCase

from alerting.models import AlertConfiguration, AlertDetection, AlertType, Severity
from alerting.services import alert_detector


class DetectionFixture(TestCase):
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

        def lot(n):
            return Parcel.objects.create(program=cls.program, dataset=cls.ds, lot_number=n)

        def sale(num, parcel, paid):
            sf = SaleFile.objects.create(sale_number=num, program=cls.program, customer=cust,
                                         parcel=parcel, agreed_price=100_000_000, net_price=100_000_000)
            Payment.objects.create(payment_number=f"P-{num}", sale_file=sf, amount=paid,
                                   status="CONFIRMED", payment_method="BANK",
                                   payment_date=date(2026, 7, 10))
            return sf

        # A : construction 28 %, payé 70 % → écart +42 → CRITIQUE.
        cls.a = lot("18")
        ConstructionProject.objects.create(parcel=cls.a, code="CA", title="C", progress_percent=28)
        sale("A", cls.a, 70_000_000)
        # B : chantier non suivi, payé 30 % → vendu sans avancement (VIGILANCE).
        cls.b = lot("23")
        sale("B", cls.b, 30_000_000)
        # C : sur-payé (200 %) → anomalie de données.
        cls.c = lot("11")
        ConstructionProject.objects.create(parcel=cls.c, code="CC", title="C", progress_percent=10)
        sale("C", cls.c, 200_000_000)


class DetectorTests(DetectionFixture):
    def _by_type(self, detections):
        out = {}
        for d in detections:
            out.setdefault(d.alert_type, []).append(d)
        return out

    def test_run_detection_finds_each_type(self):
        det = alert_detector.run_detection(reference_date=date(2026, 7, 20), persist=True)
        by = self._by_type(det)

        gap = by.get(AlertType.PAYMENT_GT_CONSTRUCTION, [])
        self.assertEqual(len(gap), 1)                      # seulement A (B non suivi, C sur-payé exclus)
        self.assertEqual(gap[0].lot_id, self.a.id)
        self.assertEqual(gap[0].severity, Severity.CRITICAL)
        self.assertEqual(gap[0].difference, 42.0)

        snp = by.get(AlertType.SOLD_NO_PROGRESS, [])
        self.assertTrue(any(d.lot_id == self.b.id for d in snp))

        dq = by.get(AlertType.DATA_QUALITY, [])
        self.assertTrue(any(d.lot_id == self.c.id for d in dq))
        self.assertEqual(dq[0].severity, Severity.IMPORTANT)

        # Persistées.
        self.assertEqual(AlertDetection.objects.count(), len(det))

    def test_detection_is_idempotent_per_period(self):
        alert_detector.run_detection(reference_date=date(2026, 7, 20), persist=True)
        n1 = AlertDetection.objects.count()
        alert_detector.run_detection(reference_date=date(2026, 7, 20), persist=True)
        self.assertEqual(AlertDetection.objects.count(), n1)  # pas de doublon

    def test_minimum_severity_filter(self):
        cfg = AlertConfiguration.objects.create(name="DG", minimum_severity=Severity.IMPORTANT)
        det = alert_detector.run_detection(configuration=cfg, reference_date=date(2026, 7, 20),
                                           persist=False)
        self.assertTrue(det)
        self.assertTrue(all(d.severity in (Severity.IMPORTANT, Severity.CRITICAL) for d in det))
        # la VIGILANCE (vendu sans avancement de B) est filtrée
        self.assertFalse(any(d.lot_id == self.b.id and d.severity == Severity.VIGILANCE for d in det))

    def test_recommendations(self):
        det = alert_detector.run_detection(reference_date=date(2026, 7, 20), persist=False)
        recos = alert_detector.generate_recommendations(det)
        self.assertTrue(recos)
        self.assertTrue(any("Prioriser les travaux sur les lots" in r for r in recos))
        self.assertTrue(any("18" in r for r in recos))  # le lot A (n°18)
