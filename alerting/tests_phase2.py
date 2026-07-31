"""Tests Phase 2 : métriques courantes, comparaison de périodes, capture snapshots."""
from datetime import date

from django.test import TestCase

from alerting.models import (
    CommercializationSnapshot, ConstructionProgressSnapshot, PaymentSnapshot,
)
from alerting.services import metrics, snapshot_service


class CompareTests(TestCase):
    def test_points_and_relative(self):
        c = metrics.compare(20, 16)
        self.assertEqual(c["current"], 20.0)
        self.assertEqual(c["previous"], 16.0)
        self.assertEqual(c["variation_points"], 4.0)      # +4 points
        self.assertEqual(c["variation_relative"], 25.0)   # +25 %

    def test_no_previous(self):
        c = metrics.compare(20, None)
        self.assertEqual(c["current"], 20.0)
        self.assertIsNone(c["variation_points"])
        self.assertIsNone(c["variation_relative"])

    def test_none_current(self):
        c = metrics.compare(None, 10)
        self.assertIsNone(c["current"])
        self.assertIsNone(c["variation_points"])


class MetricsFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        from parcelaire.models import (
            ConstructionProject, Country, Customer, Parcel, ParcelDataset,
            Payment, ProgramBlock, ProjetImmobilier, RealEstateProgram, SaleFile,
        )
        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(code="KOT", nom="Kaydan", country=cls.country)
        cls.program = RealEstateProgram.objects.create(
            code="KOTIBE", name="Kotibe", slug="kotibe", country=cls.country, project=cls.project)
        cls.block = ProgramBlock.objects.create(program=cls.program, code="IL4", label="Îlot 4")
        cls.ds = ParcelDataset.objects.create(name="DS", program=cls.program)
        # 4 lots dans l'îlot 4 ; L1 vendu + construction 20 %, les autres disponibles.
        cls.lots = [Parcel.objects.create(program=cls.program, dataset=cls.ds, block=cls.block,
                                          lot_number=str(i)) for i in range(1, 5)]
        ConstructionProject.objects.create(parcel=cls.lots[0], code="CP1", title="C", progress_percent=20)
        cls.customer = Customer.objects.create(customer_type="INDIVIDUAL", last_name="Koné")
        cls.sale = SaleFile.objects.create(sale_number="V-K-1", program=cls.program,
                                           customer=cls.customer, parcel=cls.lots[0],
                                           agreed_price=100_000_000, net_price=100_000_000)
        Payment.objects.create(payment_number="P-K-1", sale_file=cls.sale, amount=29_000_000,
                               status="CONFIRMED", payment_method="BANK", payment_date=date(2026, 7, 10))
        cls.ref = date(2026, 7, 20)
        cls.prev = date(2026, 7, 13)


class CurrentMetricsTests(MetricsFixture):
    def test_current_values(self):
        self.assertEqual(metrics.program_construction(self.program), 20.0)  # moyenne sur les suivies
        self.assertEqual(metrics.program_payment(self.program)["rate"], 29.0)
        com = metrics.program_commercialization(self.program)
        self.assertEqual(com["sold"], 1)
        self.assertEqual(com["total"], 4)
        self.assertEqual(com["rate"], 25.0)


class PeriodMetricsTests(MetricsFixture):
    def test_program_evolution_from_snapshots(self):
        ConstructionProgressSnapshot.objects.create(program=self.program, recorded_at=self.prev,
                                                    progress_percent=16)
        PaymentSnapshot.objects.create(program=self.program, recorded_at=self.prev, payment_rate=25)
        CommercializationSnapshot.objects.create(program=self.program, recorded_at=self.prev,
                                                 commercialization_rate=20)
        m = metrics.program_period_metrics(self.program, reference_date=self.ref, window_days=7)
        self.assertEqual(m["construction"], {"current": 20.0, "previous": 16.0,
                                             "variation_points": 4.0, "variation_relative": 25.0})
        self.assertEqual(m["payment"]["variation_points"], 4.0)     # 29 - 25
        self.assertEqual(m["commercialization"]["variation_points"], 5.0)  # 25 - 20
        self.assertEqual(m["gap_points"], 9.0)                      # 29 - 20
        self.assertEqual(m["sold"], 1)

    def test_block_evolution_and_ranking(self):
        ConstructionProgressSnapshot.objects.create(program=self.program, block=self.block,
                                                    recorded_at=self.prev, progress_percent=18)
        blocks = metrics.block_period_metrics(self.program, reference_date=self.ref, window_days=7)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["construction"]["variation_points"], 2.0)  # 20 - 18
        self.assertEqual(blocks[0]["rank"], 1)


class SnapshotCaptureTests(MetricsFixture):
    def test_capture_is_idempotent(self):
        w1 = snapshot_service.capture_program(self.program, recorded_at=self.ref)
        # 1 construction programme + 1 construction îlot + 1 paiement + 1 commercialisation.
        self.assertEqual(w1, 4)
        self.assertEqual(ConstructionProgressSnapshot.objects.count(), 2)
        self.assertEqual(PaymentSnapshot.objects.count(), 1)
        self.assertEqual(CommercializationSnapshot.objects.count(), 1)
        # Relancer le même jour ne duplique pas.
        snapshot_service.capture_program(self.program, recorded_at=self.ref)
        self.assertEqual(ConstructionProgressSnapshot.objects.count(), 2)
        self.assertEqual(PaymentSnapshot.objects.count(), 1)
        # Les valeurs capturées correspondent au live.
        pay_snap = PaymentSnapshot.objects.get()
        self.assertEqual(pay_snap.payment_rate, 29.0)
