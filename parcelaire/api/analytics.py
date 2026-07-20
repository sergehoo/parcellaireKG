"""
Moteur d'analyse décisionnel du tableau de bord (« centre de commandement »).

Toutes les analyses sont calculées à partir des DONNÉES RÉELLES du système
(ventes, paiements confirmés, avancement des chantiers, valeur hypothécaire).
Aucune donnée n'est simulée ; les dimensions sans source (VRD, stocks,
ouvriers, fournisseurs…) sont volontairement absentes.

Concepts clés :
- IDCP (Indice de Déséquilibre Construction / Paiement) = % payé − % construit
  par dossier de vente. Positif ⇒ le client finance plus vite que l'avancement
  des travaux (risque de sur-financement / contentieux).
- Score de santé programme = composite (avancement, encaissement,
  commercialisation) sur 100, sur les dimensions disponibles.
"""
import csv
import logging
from decimal import Decimal

from django.db import connection, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Erreurs qui signalent un broker Celery injoignable (à distinguer d'un bug
# applicatif, qui lui doit remonter). kombu.OperationalError est levée par
# .delay() quand la connexion au broker échoue ; OSError couvre le refus de
# connexion brut (ConnectionRefusedError).
try:  # pragma: no cover - dépend de la présence de kombu (fourni par celery)
    from kombu.exceptions import OperationalError as _KombuOperationalError
    _BROKER_ERRORS = (_KombuOperationalError, OSError)
except Exception:  # pragma: no cover
    _BROKER_ERRORS = (OSError,)

# Clé stable d'un verrou consultatif PostgreSQL : sérialise les recalculs
# synchrones concurrents (un seul à la fois) sans dépendre de Redis.
_REGEN_LOCK_KEY = 4726351


def _try_regen_lock():
    """Tente de prendre le verrou consultatif (portée transaction). Renvoie
    False si un autre recalcul le détient déjà. À appeler dans une
    transaction : le verrou est libéré automatiquement à sa clôture."""
    with connection.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_xact_lock(%s)", [_REGEN_LOCK_KEY])
        return bool(cur.fetchone()[0])

from parcelaire.models import (
    Alert,
    ConstructionProject,
    Customer,
    Parcel,
    Payment,
    ProjetImmobilier,
    RealEstateProgram,
    Reservation,
    SaleFile,
)


def fmt_money(v):
    try:
        return f"{int(Decimal(v or 0)):,}".replace(",", " ") + " FCFA"
    except Exception:
        return "—"


def pct(num, den):
    try:
        num = float(num or 0); den = float(den or 0)
        return round(num / den * 100, 1) if den else 0.0
    except Exception:
        return 0.0


def criticality(idcp):
    """Niveau de criticité d'après l'IDCP (% payé − % construit)."""
    if idcp >= 40:
        return ('CRITIQUE', 'Paiement très en avance sur la construction')
    if idcp >= 20:
        return ('ELEVE', 'Paiement en avance sur la construction')
    if idcp >= 8:
        return ('MOYEN', 'Paiement légèrement en avance')
    if idcp > -8:
        return ('FAIBLE', 'Paiement conforme à la construction')
    return ('INFO', 'Construction en avance sur les paiements')


def _construction_by_parcel():
    """parcel_id → avancement construction (%) le plus élevé."""
    out = {}
    for pid, prog in ConstructionProject.objects.filter(parcel_id__isnull=False).values_list('parcel_id', 'progress_percent'):
        p = float(prog or 0)
        if pid not in out or p > out[pid]:
            out[pid] = p
    return out


def _sale_rows(can_fin):
    """Une ligne d'analyse IDCP par dossier de vente actif rattaché à une parcelle."""
    con = _construction_by_parcel()
    sales = (
        SaleFile.objects.filter(is_active=True, parcel_id__isnull=False)
        .select_related('customer', 'program', 'parcel')
        .annotate(paid=Coalesce(Sum('payments__amount', filter=Q(payments__status='CONFIRMED')), Decimal('0')))
    )
    rows = []
    for s in sales:
        net = float(s.net_price or 0)
        paid = float(s.paid or 0)
        pay_pct = pct(paid, net)
        con_pct = round(con.get(s.parcel_id, 0.0), 1)
        idcp = round(pay_pct - con_pct, 1)
        level, reason = criticality(idcp)
        rows.append({
            'sale_id': s.id,
            'customer': str(s.customer) if s.customer_id else '—',
            'program': s.program.name if s.program_id else '—',
            'program_id': s.program_id,
            'lot': (s.parcel.lot_number or s.parcel.parcel_code or f'#{s.parcel_id}') if s.parcel_id else '—',
            'parcel_id': s.parcel_id,
            'paid': fmt_money(paid) if can_fin else 'Masqué',
            'paid_value': paid if can_fin else None,
            'payment_pct': pay_pct,
            'construction_pct': con_pct,
            'idcp': idcp,
            'level': level,
            'reason': reason,
            'site_manager': (getattr(s.parcel, 'metadata', {}) or {}).get('site_manager') or '—',
            'sales_agent': s.sales_agent or '—',
            'sale_date': s.sale_date.isoformat() if s.sale_date else None,
        })
    return rows


LEVEL_ORDER = {'CRITIQUE': 0, 'ELEVE': 1, 'MOYEN': 2, 'FAIBLE': 3, 'INFO': 4}


def health_band(score):
    if score >= 80:
        return 'Excellent'
    if score >= 65:
        return 'Bon'
    if score >= 50:
        return 'Sous surveillance'
    if score >= 35:
        return 'Critique'
    return 'Urgence'


class _Echo:
    """Buffer factice : write() renvoie la valeur, pour csv.writer + streaming."""
    def write(self, value):
        return value


# Préfixes qui, en tête de cellule, sont interprétés comme des formules par
# Excel/Sheets (injection CSV). On neutralise en préfixant d'une apostrophe.
_CSV_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _csv_safe(value):
    if isinstance(value, str) and value and value[0] in _CSV_FORMULA_PREFIXES:
        return "'" + value
    return value


def csv_streaming_response(filename, header, rows_iter):
    """StreamingHttpResponse CSV (UTF-8 + BOM pour Excel), en flux — ne
    matérialise pas tout l'export en mémoire. Les cellules sont neutralisées
    contre l'injection de formules."""
    writer = csv.writer(_Echo())

    def generate():
        yield '﻿'  # BOM : Excel interprète correctement les accents.
        yield writer.writerow(header)
        for row in rows_iter:
            yield writer.writerow([_csv_safe(c) for c in row])

    resp = StreamingHttpResponse(generate(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp


def _at_risk_rows(request, can_fin):
    """Lignes IDCP filtrées (level / program / min_idcp) et triées par IDCP
    décroissant. Partagé par la liste paginée et l'export CSV."""
    rows = _sale_rows(can_fin)
    level = request.query_params.get('level')
    program = request.query_params.get('program')
    try:
        min_idcp = float(request.query_params.get('min_idcp')) if request.query_params.get('min_idcp') else None
    except ValueError:
        min_idcp = None
    if level:
        rows = [r for r in rows if r['level'] == level]
    if program:
        rows = [r for r in rows if str(r['program_id']) == str(program)]
    if min_idcp is not None:
        rows = [r for r in rows if r['idcp'] >= min_idcp]
    rows.sort(key=lambda r: -r['idcp'])
    return rows


def _can_view_financial(user):
    """Droit de voir les montants financiers (superuser ou permission)."""
    return bool(user.is_superuser or user.has_perm('parcelaire.view_financial_data'))


@extend_schema_view(get=extend_schema(
    summary="Synthèse du tableau de bord",
    description="KPIs stratégiques, santé des programmes, alertes métier et top "
                "clients à risque. Les montants sont masqués (« Masqué ») sans "
                "la permission `view_financial_data`.",
    tags=["Analytics"],
    responses={200: OpenApiResponse(description="Objet de synthèse décisionnelle.")},
))
class AnalyticsDashboardAPIView(APIView):
    """GET /api/analytics/dashboard/ — synthèse exécutive : KPIs, santé des
    programmes, alertes métier, top clients à risque."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(self.build_dashboard(_can_view_financial(request.user)))

    def build_dashboard(self, can_fin):
        """Synthèse exécutive (KPIs, santé programmes, alertes, clients à
        risque). Partagée par l'API JSON, le rapport PDF et l'envoi planifié.
        `can_fin=True` ⇒ montants visibles, `False` ⇒ masqués."""
        parcels = Parcel.objects.filter(is_active=True)
        sales = SaleFile.objects.filter(is_active=True)
        ca = sales.aggregate(s=Coalesce(Sum('net_price'), Decimal('0')))['s']
        paid = Payment.objects.filter(status='CONFIRMED').aggregate(s=Coalesce(Sum('amount'), Decimal('0')))['s']
        hypo = parcels.aggregate(s=Coalesce(Sum('valeur_hypothecaire'), Decimal('0')))['s']
        con_avg = ConstructionProject.objects.aggregate(a=Coalesce(Sum('progress_percent'), Decimal('0')), n=Count('id'))
        construction_avg = round(float(con_avg['a']) / con_avg['n'], 1) if con_avg['n'] else 0.0

        by_status = dict(parcels.values_list('commercial_status').annotate(n=Count('id')).values_list('commercial_status', 'n'))
        total_parcels = parcels.count()
        # Commercialisation calculée d'après les VENTES réelles : le champ
        # commercial_status des parcelles n'est pas fiable ici (resté
        # « AVAILABLE » malgré des ventes existantes).
        sold = SaleFile.objects.filter(is_active=True, parcel_id__isnull=False).values('parcel_id').distinct().count()
        reserved = Reservation.objects.filter(is_active=True, parcel_id__isnull=False).values('parcel_id').distinct().count()

        rows = _sale_rows(can_fin)
        idcp_vals = [r['idcp'] for r in rows]
        idcp_avg = round(sum(idcp_vals) / len(idcp_vals), 1) if idcp_vals else 0.0
        crit_count = sum(1 for r in rows if r['level'] == 'CRITIQUE')
        high_count = sum(1 for r in rows if r['level'] == 'ELEVE')

        # KPIs stratégiques (dimensions disponibles).
        kpis = {
            'ca_potentiel': fmt_money(ca) if can_fin else 'Masqué',
            'encaisse': fmt_money(paid) if can_fin else 'Masqué',
            'reste_a_encaisser': fmt_money(ca - paid) if can_fin else 'Masqué',
            'taux_encaissement': pct(paid, ca),
            'valeur_hypothecaire': fmt_money(hypo) if can_fin else 'Masqué',
            'couverture_hypothecaire': pct(paid, hypo),
            'avancement_construction_moyen': construction_avg,
            'taux_commercialisation': pct(sold, total_parcels),
            'taux_reservation': pct(reserved, total_parcels),
            'idcp_moyen': idcp_avg,
            'clients_critiques': crit_count,
            'clients_eleves': high_count,
        }

        counts = {
            'projects': ProjetImmobilier.objects.filter(is_active=True).count(),
            'programs': RealEstateProgram.objects.filter(is_active=True).count(),
            'parcels': total_parcels,
            'customers': Customer.objects.filter(is_active=True).count(),
            'sales': sales.count(),
            'reservations': Reservation.objects.filter(is_active=True).count(),
        }

        # Santé des programmes.
        programs = self._programs_health(can_fin)

        # Alertes métier (règles sur données réelles).
        alerts = self._alerts(rows, parcels, sales)

        # Top clients à risque.
        top_risk = sorted(rows, key=lambda r: (-r['idcp']))[:8]

        return {
            'can_view_financial': can_fin,
            'counts': counts,
            'kpis': kpis,
            'parcels_by_status': [{'status': k or '—', 'count': v} for k, v in sorted(by_status.items(), key=lambda x: -x[1])],
            'programs_health': programs,
            'alerts': alerts,
            'clients_at_risk': top_risk,
            'at_risk_total': sum(1 for r in rows if r['level'] in ('CRITIQUE', 'ELEVE')),
        }

    def _programs_health(self, can_fin):
        out = []
        for prog in RealEstateProgram.objects.filter(is_active=True).select_related('project'):
            p_parcels = Parcel.objects.filter(program=prog, is_active=True)
            total = p_parcels.count()
            if not total:
                continue
            sold = SaleFile.objects.filter(program=prog, is_active=True, parcel_id__isnull=False).values('parcel_id').distinct().count()
            con = ConstructionProject.objects.filter(parcel__program=prog).aggregate(
                a=Coalesce(Sum('progress_percent'), Decimal('0')), n=Count('id'))
            construction = round(float(con['a']) / con['n'], 1) if con['n'] else 0.0
            p_sales = SaleFile.objects.filter(program=prog, is_active=True)
            net = p_sales.aggregate(s=Coalesce(Sum('net_price'), Decimal('0')))['s']
            paid = Payment.objects.filter(status='CONFIRMED', sale_file__program=prog).aggregate(
                s=Coalesce(Sum('amount'), Decimal('0')))['s']
            payment = pct(paid, net)
            commercialisation = pct(sold, total)
            score = round(0.35 * construction + 0.35 * min(payment, 100) + 0.30 * commercialisation, 0)
            out.append({
                'id': prog.id, 'name': prog.name,
                'project': prog.project.nom if prog.project_id else '—',
                'parcels': total, 'sold': sold,
                'construction': construction, 'payment': payment,
                'commercialisation': commercialisation,
                'score': int(score), 'band': health_band(score),
                'ca': fmt_money(net) if can_fin else 'Masqué',
                'encaisse': fmt_money(paid) if can_fin else 'Masqué',
            })
        return sorted(out, key=lambda x: x['score'])

    def _alerts(self, rows, parcels, sales):
        alerts = []

        def add(key, label, level, count, detail):
            if count:
                alerts.append({'key': key, 'label': label, 'level': level, 'count': count, 'detail': detail})

        add('idcp_critique', 'Paiement très en avance sur la construction', 'CRITIQUE',
            sum(1 for r in rows if r['level'] == 'CRITIQUE'), 'IDCP ≥ 40 % — risque de sur-financement / contentieux')
        add('idcp_eleve', 'Paiement en avance sur la construction', 'ELEVE',
            sum(1 for r in rows if r['level'] == 'ELEVE'), 'IDCP 20–40 %')
        add('construction_retard', 'Construction très en retard', 'ELEVE',
            sum(1 for r in rows if r['construction_pct'] < 20 and r['payment_pct'] > 40),
            'Avancement < 20 % alors que le paiement dépasse 40 %')
        add('titre_manquant', 'Titre foncier manquant (lot vendu)', 'MOYEN',
            parcels.filter(commercial_status='SOLD', has_title_document=False).count(),
            'Parcelle vendue sans document de titre foncier')
        add('contrat_non_signe', 'Dossier de vente non signé avec paiements', 'MOYEN',
            sales.filter(status__in=['OPEN', 'PENDING_DOCS', 'PENDING_PAYMENT'], payments__status='CONFIRMED')
                 .distinct().count(),
            'Paiements confirmés mais dossier non signé')
        add('hypo_insuffisante', 'Valeur hypothécaire non renseignée (lot vendu)', 'MOYEN',
            parcels.filter(commercial_status='SOLD').filter(Q(valeur_hypothecaire__isnull=True) | Q(valeur_hypothecaire=0)).count(),
            'Lot vendu sans valeur hypothécaire — couverture non garantie')
        return sorted(alerts, key=lambda a: LEVEL_ORDER.get(a['level'], 9))


@extend_schema_view(get=extend_schema(
    summary="Rapport PDF du tableau de bord",
    description="Génère et télécharge le rapport PDF exécutif (WeasyPrint). "
                "Masquage financier selon les droits de l'utilisateur.",
    tags=["Analytics"],
    responses={(200, "application/pdf"): OpenApiTypes.BINARY},
))
class DashboardReportPDFView(APIView):
    """GET /api/analytics/dashboard/report/ — rapport PDF exécutif du Centre
    de commandement (mêmes données réelles que le dashboard, masquage
    financier respecté). Rendu HTML → PDF via WeasyPrint."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'report'

    def get(self, request):
        can_fin = _can_view_financial(request.user)
        username = request.user.get_full_name() or request.user.get_username()
        pdf = render_dashboard_pdf(can_fin, username)
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = 'attachment; filename="tableau-de-bord.pdf"'
        return resp


def render_dashboard_pdf(can_fin, username='—'):
    """Rend le rapport PDF exécutif du Centre de pilotage et renvoie les octets.
    Réutilisé par l'endpoint HTTP et par l'envoi planifié. Import WeasyPrint
    tardif (libs natives libgobject via cffi)."""
    data = AnalyticsDashboardAPIView().build_dashboard(can_fin)
    html = render_to_string('parcelaire/reports/dashboard_report.html', {
        'd': data,
        'generated_at': timezone.now(),
        'username': username,
    })
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


class AtRiskPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema_view(get=extend_schema(
    summary="Clients à risque (IDCP)",
    description="Liste paginée des dossiers classés par Indice de Déséquilibre "
                "Construction/Paiement décroissant. Montants masqués sans "
                "`view_financial_data`.",
    tags=["Analytics"],
    parameters=[
        OpenApiParameter("level", str, description="Filtre par niveau (CRITIQUE, ELEVE, MOYEN, FAIBLE, INFO)."),
        OpenApiParameter("program", int, description="Filtre par identifiant de programme."),
        OpenApiParameter("min_idcp", float, description="IDCP minimum (%)."),
        OpenApiParameter("page", int), OpenApiParameter("page_size", int),
    ],
    responses={200: OpenApiResponse(description="Page de dossiers à risque.")},
))
class AtRiskClientsAPIView(APIView):
    """GET /api/analytics/at-risk/ — liste complète, filtrable, des clients
    classés par IDCP décroissant. Filtres : level, program, min_idcp."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        can_fin = u.is_superuser or u.has_perm('parcelaire.view_financial_data')
        rows = _at_risk_rows(request, can_fin)
        paginator = AtRiskPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


@extend_schema_view(get=extend_schema(
    summary="Export CSV des clients à risque",
    description="Mêmes filtres que la liste. Montants masqués sans "
                "`view_financial_data`. Débit limité (throttle « export »).",
    tags=["Analytics"],
    responses={(200, "text/csv"): OpenApiTypes.STR},
))
class AtRiskExportAPIView(APIView):
    """GET /api/analytics/at-risk/export/ — export CSV des clients à risque
    (mêmes filtres que la liste). Les montants financiers restent masqués
    pour les utilisateurs sans view_financial_data."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'export'

    def get(self, request):
        u = request.user
        can_fin = u.is_superuser or u.has_perm('parcelaire.view_financial_data')
        rows = _at_risk_rows(request, can_fin)
        header = [
            'Client', 'Programme', 'Lot', 'Payé', 'Paiement %', 'Construction %',
            'IDCP %', 'Niveau', 'Motif', 'Chef de chantier', 'Commercial', 'Date de vente',
        ]

        def lines():
            for r in rows:
                yield [
                    r['customer'], r['program'], r['lot'], r['paid'], r['payment_pct'],
                    r['construction_pct'], r['idcp'], r['level'], r['reason'],
                    r['site_manager'], r['sales_agent'], r['sale_date'] or '',
                ]
        return csv_streaming_response('clients-a-risque.csv', header, lines())


# =====================================================================
# Centre de notifications — alertes persistées / auditables
# =====================================================================

def serialize_alert(a):
    return {
        'id': a.id,
        'rule': a.rule,
        'level': a.level,
        'level_display': a.get_level_display(),
        'status': a.status,
        'status_display': a.get_status_display(),
        'title': a.title,
        'detail': a.detail or '',
        'metric': a.metric or '',
        'program': a.program.name if a.program_id else None,
        'program_id': a.program_id,
        'lot': (a.parcel.lot_number or a.parcel.parcel_code or f'#{a.parcel_id}') if a.parcel_id else None,
        'parcel_id': a.parcel_id,
        'customer': str(a.customer) if a.customer_id else None,
        'customer_id': a.customer_id,
        'sale_id': a.sale_file_id,
        'first_detected_at': a.first_detected_at.isoformat() if a.first_detected_at else None,
        'last_detected_at': a.last_detected_at.isoformat() if a.last_detected_at else None,
        'acknowledged_by': a.acknowledged_by.get_username() if a.acknowledged_by_id else None,
        'acknowledged_at': a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        'resolved_at': a.resolved_at.isoformat() if a.resolved_at else None,
    }


class AlertPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 200


def _filter_alerts_qs(request):
    """Queryset d'alertes filtré (level / status / rule / program). Par
    défaut les alertes résolues sont masquées. Partagé par la liste et
    l'export CSV."""
    qs = Alert.objects.select_related('program', 'parcel', 'customer').all()
    p = request.query_params
    if p.get('level'):
        qs = qs.filter(level=p['level'])
    if p.get('status'):
        qs = qs.filter(status=p['status'])
    else:
        qs = qs.exclude(status='RESOLVED')
    if p.get('rule'):
        qs = qs.filter(rule=p['rule'])
    if p.get('program'):
        qs = qs.filter(program_id=p['program'])
    if p.get('parcel'):
        qs = qs.filter(parcel_id=p['parcel'])
    return qs


@extend_schema_view(get=extend_schema(
    summary="Liste des alertes",
    description="Alertes métier persistées, filtrables. Par défaut, les alertes "
                "résolues sont masquées. Renvoie aussi des compteurs et le drapeau "
                "`can_manage`.",
    tags=["Alertes"],
    parameters=[
        OpenApiParameter("level", str, description="CRITIQUE, ELEVE, MOYEN, FAIBLE, INFO."),
        OpenApiParameter("status", str, description="NEW, ACK, RESOLVED."),
        OpenApiParameter("rule", str, description="Code de règle (idcp, titre_manquant, …)."),
        OpenApiParameter("program", int), OpenApiParameter("parcel", int),
        OpenApiParameter("page", int), OpenApiParameter("page_size", int),
    ],
    responses={200: OpenApiResponse(description="Page d'alertes + compteurs.")},
))
class AlertListAPIView(APIView):
    """GET /api/alerts/ — centre de notifications : alertes persistées,
    filtrables (level, status, rule, program). Renvoie aussi des compteurs."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _filter_alerts_qs(request)

        counts = {
            'new': Alert.objects.filter(status='NEW').count(),
            'ack': Alert.objects.filter(status='ACK').count(),
            'resolved': Alert.objects.filter(status='RESOLVED').count(),
            'critique': Alert.objects.filter(status__in=['NEW', 'ACK'], level='CRITIQUE').count(),
        }

        paginator = AlertPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        resp = paginator.get_paginated_response([serialize_alert(a) for a in page])
        resp.data['counts'] = counts
        resp.data['can_manage'] = bool(
            request.user.is_superuser or request.user.has_perm('parcelaire.change_alert'))
        return resp


@extend_schema_view(get=extend_schema(
    summary="Export CSV des alertes",
    description="Mêmes filtres que la liste. Débit limité (throttle « export »).",
    tags=["Alertes"],
    responses={(200, "text/csv"): OpenApiTypes.STR},
))
class AlertExportAPIView(APIView):
    """GET /api/alerts/export/ — export CSV des alertes (mêmes filtres que la
    liste). Ordre stable : plus récemment détectées d'abord."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'export'

    def get(self, request):
        qs = _filter_alerts_qs(request).order_by('-last_detected_at')
        header = [
            'Niveau', 'Statut', 'Règle', 'Titre', 'Détail', 'Indicateur',
            'Programme', 'Lot', 'Client', 'Détectée le', 'Dernière détection',
            'Accusée par', 'Résolue le',
        ]

        def lines():
            for a in qs.iterator():
                d = serialize_alert(a)
                yield [
                    d['level_display'], d['status_display'], d['rule'], d['title'],
                    d['detail'], d['metric'], d['program'] or '', d['lot'] or '',
                    d['customer'] or '', d['first_detected_at'] or '',
                    d['last_detected_at'] or '', d['acknowledged_by'] or '',
                    d['resolved_at'] or '',
                ]
        return csv_streaming_response('alertes.csv', header, lines())


@extend_schema_view(post=extend_schema(
    summary="Action sur une alerte",
    description="Accuser (ack), résoudre (resolve) ou rouvrir (reopen) une alerte. "
                "Traçable (qui / quand). Exige la permission `change_alert`.",
    tags=["Alertes"],
    parameters=[
        OpenApiParameter("pk", int, OpenApiParameter.PATH, description="Identifiant de l'alerte."),
        OpenApiParameter("action", str, OpenApiParameter.PATH, description="ack | resolve | reopen."),
    ],
    request=None,
    responses={200: OpenApiResponse(description="Alerte mise à jour."),
               403: OpenApiResponse(description="Permission requise (change_alert).")},
))
class AlertActionAPIView(APIView):
    """POST /api/alerts/<pk>/<action>/ — action = ack | resolve | reopen.
    Traçable (qui / quand). Exige la permission change_alert."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, action):
        if not (request.user.is_superuser or request.user.has_perm('parcelaire.change_alert')):
            return Response({'detail': "Permission requise (change_alert)."}, status=403)
        alert = get_object_or_404(Alert, pk=pk)
        now = timezone.now()
        if action == 'ack':
            alert.status = 'ACK'
            alert.acknowledged_by = request.user
            alert.acknowledged_at = now
        elif action == 'resolve':
            alert.status = 'RESOLVED'
            alert.resolved_at = now
        elif action == 'reopen':
            alert.status = 'NEW'
            alert.resolved_at = None
            alert.acknowledged_by = None
            alert.acknowledged_at = None
        else:
            return Response({'detail': 'Action inconnue.'}, status=400)
        alert.save()
        return Response(serialize_alert(alert))


@extend_schema_view(get=extend_schema(
    summary="Compteurs d'alertes actives",
    description="Compteurs d'alertes ACTIVES (NEW+ACK) par niveau — endpoint léger "
                "pour le badge de navigation.",
    tags=["Alertes"],
    responses={200: OpenApiResponse(
        description="Compteurs par niveau.",
        examples=[OpenApiExample("Exemple", value={
            "critique": 94, "eleve": 138, "active_total": 1357,
            "by_level": {"CRITIQUE": 94, "ELEVE": 138, "MOYEN": 1125}})])},
))
class AlertSummaryAPIView(APIView):
    """GET /api/alerts/summary/ — compteurs d'alertes ACTIVES (NEW+ACK) par
    niveau, pour le badge de la barre de navigation.

    Volontairement minimal : un seul COUNT groupé (adossé à l'index composite
    (status, level)), aucune hydratation de ligne ni sérialisation — bien plus
    léger que /api/alerts/ pour un endpoint sondé à intervalle régulier.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        by_level = dict(
            Alert.objects.filter(status__in=['NEW', 'ACK'])
            .order_by()  # neutralise l'ordering Meta pour un GROUP BY propre
            .values('level')
            .annotate(n=Count('id'))
            .values_list('level', 'n')
        )
        return Response({
            'critique': by_level.get('CRITIQUE', 0),
            'eleve': by_level.get('ELEVE', 0),
            'active_total': sum(by_level.values()),
            'by_level': by_level,
        })


@extend_schema_view(get=extend_schema(
    summary="Sévérité d'alerte par entité (carte)",
    description="Sévérité d'alerte ACTIVE par parcelle et par programme, pour le "
                "surlignage de la carte : {by_parcel, by_program} avec pire niveau "
                "et total par entité.",
    tags=["Alertes"],
    parameters=[OpenApiParameter(
        "levels", str, description="Filtre CSV de niveaux (ex. CRITIQUE,ELEVE).")],
    responses={200: OpenApiResponse(
        description="Sévérités par entité.",
        examples=[OpenApiExample("Exemple", value={
            "by_parcel": {"1765": {"level": "CRITIQUE", "count": 2}},
            "by_program": {"6": {"level": "ELEVE", "count": 40}}})])},
))
class AlertMapAPIView(APIView):
    """GET /api/alerts/map/ — sévérité d'alerte ACTIVE (NEW+ACK) par entité
    géographique, pour surligner la carte. Renvoie {by_parcel, by_program}
    où chaque entrée = {level: pire niveau, count: total}. Filtre optionnel
    ?levels=CRITIQUE,ELEVE. Uniquement des compteurs (aucune ligne hydratée)."""
    permission_classes = [IsAuthenticated]
    ACTIVE = ['NEW', 'ACK']

    @staticmethod
    def _worst_map(rows):
        out = {}
        for eid, level, n in rows:
            e = out.get(eid)
            if e is None:
                out[eid] = {'level': level, 'count': n}
            else:
                e['count'] += n
                if LEVEL_ORDER.get(level, 9) < LEVEL_ORDER.get(e['level'], 9):
                    e['level'] = level
        return out

    def get(self, request):
        levels = [x for x in (request.query_params.get('levels') or '').split(',') if x]
        # .order_by() neutralise l'ordering Meta (-last_detected_at) : sans lui,
        # certaines versions de Django l'injecteraient dans le GROUP BY et
        # sur-découperaient les agrégats.
        base = Alert.objects.filter(status__in=self.ACTIVE).order_by()
        if levels:
            base = base.filter(level__in=levels)
        # .order_by() vide : neutralise tout Meta.ordering pour garantir un
        # GROUP BY (entité, niveau) net — un seul agrégat par couple.
        parcel_rows = (base.filter(parcel_id__isnull=False)
                       .values_list('parcel_id', 'level').annotate(n=Count('id')).order_by())
        program_rows = (base.filter(program_id__isnull=False)
                        .values_list('program_id', 'level').annotate(n=Count('id')).order_by())
        return Response({
            'by_parcel': self._worst_map(parcel_rows),
            'by_program': self._worst_map(program_rows),
        })


@extend_schema_view(post=extend_schema(
    summary="Recalcul des alertes à la demande",
    description="Relance le moteur d'alertes (async via Celery si le broker répond, "
                "sinon recalcul synchrone). Exige la permission `change_alert`.",
    tags=["Alertes"],
    request=None,
    responses={202: OpenApiResponse(description="Recalcul lancé (async)."),
               200: OpenApiResponse(description="Recalcul synchrone effectué."),
               403: OpenApiResponse(description="Permission requise (change_alert).")},
))
class AlertRegenerateAPIView(APIView):
    """POST /api/alerts/regenerate/ — recalcul à la demande des alertes.

    Chemin normal : délègue la tâche idempotente à Celery (202, asynchrone).
    Si — et seulement si — le broker est injoignable, repli sur un recalcul
    SYNCHRONE, protégé par un verrou consultatif PostgreSQL qui empêche les
    recalculs concurrents (un seul à la fois, sinon 409). Exige change_alert.
    """
    permission_classes = [IsAuthenticated]
    throttle_scope = 'regenerate'

    def post(self, request):
        if not (request.user.is_superuser or request.user.has_perm('parcelaire.change_alert')):
            return Response({'detail': "Permission requise (change_alert)."}, status=403)

        # Import tardif (parcelaire.tasks importe ce module → cycle). Hors du
        # try : une erreur d'import est un vrai bug et doit remonter en 500,
        # non être confondue avec une panne de broker et masquée.
        from parcelaire.tasks import generate_alerts_task
        try:
            result = generate_alerts_task.delay()
        except _BROKER_ERRORS as exc:
            logger.warning("Broker Celery injoignable, repli sur recalcul synchrone : %s", exc)
            return self._regenerate_sync(str(exc))
        return Response(
            {'mode': 'async', 'task_id': str(result.id),
             'detail': "Recalcul lancé en arrière-plan."},
            status=202,
        )

    @staticmethod
    def _regenerate_sync(broker_error):
        """Recalcul synchrone verrouillé : un seul recalcul à la fois."""
        from parcelaire.services.alerts import generate_alerts
        with transaction.atomic():
            if not _try_regen_lock():
                return Response(
                    {'mode': 'sync', 'detail': "Un recalcul est déjà en cours.",
                     'broker_error': broker_error},
                    status=409,
                )
            summary = generate_alerts()
        return Response({'mode': 'sync', 'detail': "Recalcul effectué.",
                         'broker_error': broker_error, **summary})
