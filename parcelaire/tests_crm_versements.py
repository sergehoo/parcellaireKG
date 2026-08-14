"""API CRM mise à jour : le payé se calcule depuis l'HISTORIQUE `versements[]`
(le cumul `versement_client` est déprécié). Couvre l'ingestion (CrmLotSync) et
la projection en Payments réels (idempotence, annulation des synthétiques)."""
import os
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from parcelaire.models import (
    Country, Parcel, ParcelDataset, Payment, ProjetImmobilier, RealEstateProgram,
)
from parcelaire.services.crm_lot_sync import KaydanCRMLotSyncService
from parcelaire.services.crm_projection import ParcelCRMProjectionService

# Le constructeur du service exige les identifiants CRM (jamais appelés ici :
# on ne teste que la construction de payload, pas les requêtes HTTP).
_FAKE_CRM_ENV = {
    "EXTERNAL_LOTS_API_URL": "https://crm.test/api/crm/lots",
    "EXTERNAL_LOTS_API_KEY": "test-key",
    "EXTERNAL_LOTS_API_USERNAME": "test-user",
    "EXTERNAL_LOTS_API_PASSWORD": "test-pwd",
}


def sync_service():
    with mock.patch.dict(os.environ, _FAKE_CRM_ENV):
        return KaydanCRMLotSyncService()


def crm_item(**overrides):
    """Ligne CRM au nouveau format (échantillon réel condensé : 3 versements)."""
    item = {
        "id_lot": "1422", "lot": "243", "ilot": "18", "id_programme": "9",
        "code_projet": "KAY0096",
        "valeur_hypothecaire": "33996709.015",
        "avancement_travaux_mois": "65.009783987844",
        "matricule": "C000620", "nom": "YOUANT", "prenom": "RACHELLE",
        "cout_actif": "49305000",
        "versement_client": "11000000",   # cumul DÉPRÉCIÉ (≠ somme de l'historique)
        "ecart_status": "-67.6439",
        "unitaire_lot": "243", "unitaire_ilot": "18",
        "unitaire_libelle_type_lot": "4 PIECES BANDE",
        "unitaire_valeur_hypothecaire": "33996709.015",
        "unitaire_avancement_travaux_mois": "65.009783987844",
        "unitaire_versement_client": "7500000",
        "unitaire_code_projet": "KAY0096", "unitaire_ecart_status": "-77.939",
        "versements": [
            {"id_versement": "2478286", "matricule": "C000620", "lot": "243",
             "id_lot": "1422", "montant": "1500000", "date_versement": "2026-07-10",
             "mode_paiement": "Chèque", "date_update": "2026-08-02 21:25:54"},
            {"id_versement": "2478285", "matricule": "C000620", "lot": "243",
             "id_lot": "1422", "montant": "2000000", "date_versement": "2026-06-17",
             "mode_paiement": "Chèque", "date_update": "2026-08-02 21:25:54"},
            {"id_versement": "2480523", "matricule": "C000620", "lot": "243",
             "id_lot": "1422", "montant": "5000000", "date_versement": "2024-10-16",
             "mode_paiement": "Virement", "date_update": "2026-08-02 21:25:54"},
        ],
    }
    item.update(overrides)
    return item


class IngestionVersementsTests(TestCase):
    def setUp(self):
        self.svc = sync_service()

    def test_paid_comes_from_history_not_deprecated_field(self):
        payload = self.svc.build_sync_payload(
            items=[crm_item()], code_projet="KAY0096", lot="243", ilot="18",
            now=timezone.now())
        # 1,5M + 2M + 5M = 8,5M — PAS les 11M du cumul déprécié.
        self.assertEqual(payload["summary"]["versement_client_total"], "8500000.00")
        self.assertEqual(len(payload["units"][0]["versements"]), 3)

    def test_fallback_to_cumul_without_history(self):
        payload = self.svc.build_sync_payload(
            items=[crm_item(versements=[])], code_projet="KAY0096", lot="243",
            ilot="18", now=timezone.now())
        self.assertEqual(payload["summary"]["versement_client_total"], "11000000.00")

    def test_duplicate_versement_ids_deduplicated(self):
        item = crm_item()
        item["versements"].append(dict(item["versements"][0]))  # doublon exact
        payload = self.svc.build_sync_payload(
            items=[item], code_projet="KAY0096", lot="243", ilot="18",
            now=timezone.now())
        self.assertEqual(payload["summary"]["versement_client_total"], "8500000.00")


class ProjectionVersementsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.create(nom="Côte d'Ivoire", code="CI")
        cls.project = ProjetImmobilier.objects.create(code="KAY0096", nom="Kaydan", country=cls.country)
        cls.program = RealEstateProgram.objects.create(
            code="PRG-CRM", name="Jardins d'Ahoué", slug="jardins-ahoue",
            country=cls.country, project=cls.project)
        cls.ds = ParcelDataset.objects.create(name="DS", program=cls.program)

    def make_parcel(self, item=None):
        parcel = Parcel.objects.create(program=self.program, dataset=self.ds, lot_number="243")
        payload = sync_service().build_sync_payload(
            items=[item or crm_item()], code_projet="KAY0096", lot="243", ilot="18",
            now=timezone.now())
        parcel.metadata = {"crm_lot_sync": payload}
        parcel.save(update_fields=["metadata"])
        return parcel

    def confirmed_total(self, parcel):
        return (Payment.objects.filter(sale_file__parcel=parcel, is_active=True,
                                       status="CONFIRMED")
                .aggregate(s=Sum("amount"))["s"] or Decimal("0"))

    def test_projection_creates_real_dated_payments(self):
        parcel = self.make_parcel()
        result = ParcelCRMProjectionService().project_parcel(parcel)
        self.assertEqual(result["payment_mode"], "versements_history")
        self.assertEqual(result["versements_created"], 3)
        self.assertEqual(self.confirmed_total(parcel), Decimal("8500000.00"))
        p = Payment.objects.get(payment_number="PAY-CRM-V-2480523")
        self.assertEqual(p.amount, Decimal("5000000.00"))
        self.assertEqual(p.payment_date, date(2024, 10, 16))
        self.assertEqual(p.payment_method, "BANK")     # Virement
        cheque = Payment.objects.get(payment_number="PAY-CRM-V-2478286")
        self.assertEqual(cheque.payment_method, "CHEQUE")

    def test_projection_is_idempotent(self):
        parcel = self.make_parcel()
        svc = ParcelCRMProjectionService()
        svc.project_parcel(parcel)
        result2 = svc.project_parcel(parcel)
        self.assertEqual(result2["versements_created"], 0)
        self.assertEqual(Payment.objects.filter(sale_file__parcel=parcel).count(), 3)
        self.assertEqual(self.confirmed_total(parcel), Decimal("8500000.00"))

    def test_legacy_cumulative_payments_are_cancelled(self):
        # 1er passage à l'ANCIEN format → paiement synthétique par delta de cumul.
        parcel = self.make_parcel(item=crm_item(versements=[]))
        svc = ParcelCRMProjectionService()
        r1 = svc.project_parcel(parcel)
        self.assertEqual(r1["payment_mode"], "cumulative_delta")
        self.assertEqual(self.confirmed_total(parcel), Decimal("11000000.00"))
        # L'API passe au nouveau format → l'historique remplace le synthétique
        # (sans annulation, on compterait 11M + 8,5M).
        payload = sync_service().build_sync_payload(
            items=[crm_item()], code_projet="KAY0096", lot="243", ilot="18",
            now=timezone.now())
        parcel.refresh_from_db()
        meta = parcel.metadata or {}
        meta["crm_lot_sync"] = payload
        parcel.metadata = meta
        parcel.save(update_fields=["metadata"])
        r2 = svc.project_parcel(parcel)
        self.assertEqual(r2["legacy_payments_cancelled"], 1)
        self.assertEqual(self.confirmed_total(parcel), Decimal("8500000.00"))
        legacy = Payment.objects.filter(reference__startswith="CRM_CUMUL_").get()
        self.assertEqual(legacy.status, "CANCELLED")
        self.assertFalse(legacy.is_active)

    def test_changed_amount_is_realigned(self):
        parcel = self.make_parcel()
        svc = ParcelCRMProjectionService()
        svc.project_parcel(parcel)
        # Le CRM corrige un montant → la re-projection réaligne le Payment.
        item = crm_item()
        item["versements"][0]["montant"] = "1750000"
        payload = sync_service().build_sync_payload(
            items=[item], code_projet="KAY0096", lot="243", ilot="18",
            now=timezone.now())
        parcel.refresh_from_db()
        meta = parcel.metadata
        meta["crm_lot_sync"] = payload
        parcel.metadata = meta
        parcel.save(update_fields=["metadata"])
        r = svc.project_parcel(parcel)
        self.assertEqual(r["versements_updated"], 1)
        p = Payment.objects.get(payment_number="PAY-CRM-V-2478286")
        self.assertEqual(p.amount, Decimal("1750000.00"))
        self.assertEqual(self.confirmed_total(parcel), Decimal("8750000.00"))


class EnvB64Tests(TestCase):
    """Les secrets CRM peuvent être fournis en base64 (<NAME>_B64) pour survivre
    aux caractères spéciaux (#, $, guillemets) mutilés par les fichiers d'env."""

    def test_b64_variant_takes_precedence(self):
        import base64
        env = dict(_FAKE_CRM_ENV)
        real_password = "D@motdepasse#45#"  # contient # → intransportable en clair
        env["EXTERNAL_LOTS_API_PASSWORD"] = "tronque-sans-diese"
        env["EXTERNAL_LOTS_API_PASSWORD_B64"] = base64.b64encode(real_password.encode()).decode()
        with mock.patch.dict(os.environ, env):
            svc = KaydanCRMLotSyncService()
        self.assertEqual(svc.api_password, real_password)

    def test_plain_value_still_works(self):
        with mock.patch.dict(os.environ, _FAKE_CRM_ENV):
            svc = KaydanCRMLotSyncService()
        self.assertEqual(svc.api_password, _FAKE_CRM_ENV["EXTERNAL_LOTS_API_PASSWORD"])

    def test_invalid_b64_raises_clear_error(self):
        from django.core.exceptions import ImproperlyConfigured
        env = dict(_FAKE_CRM_ENV)
        env["EXTERNAL_LOTS_API_PASSWORD_B64"] = "pas-du-base64-!!!"
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(ImproperlyConfigured):
                KaydanCRMLotSyncService()
