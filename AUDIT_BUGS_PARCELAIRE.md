# Audit du projet `parcelaireKG` — Bugs & anomalies

Date : 6 mai 2026
Périmètre : tout le projet, focus sur le module `parcelaire` (cartographie / cadastre).
Méthode : revue statique des fichiers `parcelaire/`, `parcelaireKG/settings/`, `templates/`, `services/`, `management/commands/`, `docker-compose.yml`, `.env`, `requirements.txt`.

Légende criticité : **🔴 Critique** · **🟠 Élevée** · **🟡 Moyenne** · **🟢 Faible**

---

## 1. Sécurité & configuration (settings)

### 🔴 1.1. `DEBUG = True` en production
`parcelaireKG/settings/prod.py` ligne 5 : `DEBUG = True`. La config "prod" tourne en mode debug. Toute erreur expose les variables d'environnement, la stack, le SECRET_KEY et les chemins. À corriger immédiatement.

### 🔴 1.2. `SECRET_KEY` codée en dur, marquée `django-insecure-…`
`parcelaireKG/settings/base.py` ligne 30. Le même `SECRET_KEY` est aussi présent (commenté) dans `prod.py` et dans le `.env`. La clé doit être lue depuis l'environnement, jamais codée.

### 🔴 1.3. `.env` historiquement committé contenant des secrets en clair
Le fichier `.env` figure dans l'historique Git (commit `4cebac262`, supprimé au commit `de5c775b3`). Il contient :
- `DB_PASSWORD=weddingLIFE18`
- `EXTERNAL_LOTS_API_KEY=5632d76ece5711436d3084a628f2afb03388a373`
- `EXTERNAL_LOTS_API_USERNAME=admin` / `EXTERNAL_LOTS_API_PASSWORD=D@t@rium@1545#`

Ces secrets doivent être considérés compromis et **rotés immédiatement**, et l'historique Git nettoyé (`git filter-repo`).

### 🔴 1.4. `ALLOWED_HOSTS = ['*']` en dev (et en prod par héritage)
`parcelaireKG/settings/dev.py` ligne 9 : `ALLOWED_HOSTS = ['*']`. Le `prod.py` n'override pas, donc hérite uniquement de `base.py` (`['datarium-dev.com', 'localhost', '127.0.0.1']`) qui ne correspond pas au domaine réel de prod (`parcelaire.kaydangroupe.com`). Conséquence : la prod tourne avec un `ALLOWED_HOSTS` invalide, et le dev accepte n'importe quel hôte (vulnérable au host header poisoning).

### 🟠 1.5. `django-csp` installé mais non actif
- `csp` est dans `INSTALLED_APPS` (`base.py` l. 69)
- `csp.middleware.CSPMiddleware` **n'est pas** dans `MIDDLEWARE`
- Aucune directive `CONTENT_SECURITY_POLICY` / `CSP_DEFAULT_SRC` définie

Aucune CSP n'est donc appliquée. Cela rend les nombreux `innerHTML`/template literals des cartes (cf. §5) plus dangereux qu'ils ne devraient l'être.

### 🟠 1.6. Cookies non sécurisés en production
Aucun de ces réglages n'est défini en prod : `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER`. Le HSTS est seulement appliqué côté Traefik, pas à Django. Les cookies de session passent sans flag Secure.

### 🟠 1.7. Chemins GDAL/GEOS codés en dur (macOS)
`dev.py` lignes 13-14 :
```python
GDAL_LIBRARY_PATH = "/opt/homebrew/lib/libgdal.dylib"
GEOS_LIBRARY_PATH = "/opt/homebrew/lib/libgeos_c.dylib"
```
Ne fonctionnera ni dans Docker (Linux) ni sur un poste Linux. À conditionner par OS ou laisser Django auto-détecter via `LD_LIBRARY_PATH`.

### 🟠 1.8. `parcelaireKG/settings.py` (legacy) entièrement commenté
Le fichier subsiste à côté du package `settings/`. Source de confusion ; il faut le supprimer pour éviter qu'un import incorrect (`DJANGO_SETTINGS_MODULE=parcelaireKG.settings`) ne le vise. NB : `manage.py` pointe précisément sur `parcelaireKG.settings` — ça marche par hasard car le package l'emporte sur le module, mais c'est fragile.

### 🟡 1.9. `TIME_ZONE = 'UTC'` mais `CELERY_TIMEZONE = 'Africa/Abidjan'`
Incohérence horaire entre Django et Celery. Tâches planifiées via `crontab(hour=2, minute=0)` s'exécutent en heure d'Abidjan tandis que `auto_now_add` / `auto_now` enregistrent en UTC. Aligner les deux.

### 🟡 1.10. `CSRF_TRUSTED_ORIGINS` contient `http://datarium-dev.com`
`base.py`. Django 4 exige `https://`. Les requêtes HTTPS depuis `datarium-dev.com` sont validées, mais la ligne HTTP n'a aucun effet et génère un avertissement.

### 🟢 1.11. `prod.py` : ligne fantôme issue d'un copier-coller
Le début de `prod.py` semble fusionné avec un commentaire `gdal_translate …` du `dev.py`. À nettoyer (`prod.py` doit commencer par un docstring ou directement `from .base import *`).

---

## 2. Migrations & schéma

### 🔴 2.1. Aucune migration committée
`parcelaire/migrations/` et `ai_construction/migrations/` ne contiennent que `__init__.py`. Or :
- `parcelaire/models.py` fait 1 925 lignes avec ~40 modèles GIS, contraintes, indexes
- `ai_construction` aussi
- `db.sqlite3` (132 KB) date du 10 mars 2026 alors que les modèles ont évolué jusqu'au 21 avril

Conséquences :
- Impossible de déployer (`manage.py migrate` ne crée rien)
- L'admin et les vues plantent dès qu'on touche un champ qui n'existe pas en base (ex. `valeur_hypothecaire`, `program__orthophotos` ajoutés tardivement)
- Le `tags M2M` sur `Parcel` n'a jamais été matérialisé

À corriger : `python manage.py makemigrations parcelaire ai_construction` puis commit. Vérifier que les contraintes `UniqueConstraint(..., condition=Q(is_current=True))` sur `ProgramOrthophoto` sont bien générées.

---

## 3. Modèles (`parcelaire/models.py`)

### 🔴 3.1. `save()` qui appelle `full_clean()` partout
~15 modèles (`Place`, `RealEstateProgram`, `Parcel`, `Reservation`, `SaleFile`, `PaymentInstallment`, `Payment`, `ConstructionProject`…) appellent `self.full_clean()` dans leur `save()`. Conséquences :

1. Toute écriture `save()` re-déclenche TOUTES les validations, y compris des requêtes DB (ex. `Parcel.clean()` exécute `self.tags.exclude(program_id=self.program_id)` à chaque sauvegarde — N+1 garanti sur les imports)
2. Les services CRM (`crm_lot_sync.py`, `crm_projection.py`) qui font `parcel.save()` paient la validation à chaque tour
3. Les `bulk_*` ne déclenchent pas `clean()`, donc cohérence variable entre import bulk et save unitaire
4. Sur `ProgramOrthophoto.save()` la `full_clean()` peut faire échouer la sauvegarde initiale si `min_zoom > max_zoom` même temporairement

Recommandation : déplacer la validation au niveau formulaire/serializer ou utiliser un signal post-save dédié.

### 🟠 3.2. `Place.unique_together("country", "type", "nom", "parent")` ne fonctionne pas si `parent IS NULL`
PostgreSQL traite `NULL` comme distinct dans les contraintes uniques. On peut donc créer N régions de même nom dans le même pays sans parent. À remplacer par `UniqueConstraint(... condition=Q(parent__isnull=False))` + une seconde `UniqueConstraint(... condition=Q(parent__isnull=True))`.

### 🟠 3.3. `Place.clean()` détection de boucle incomplète
La boucle `while ancestor:` ne détecte qu'un cycle où l'objet courant est ancêtre de lui-même. Un cycle entre deux nœuds existants (A→B→A) n'est détecté que si on recharge l'enregistrement courant. Utiliser un `set()` des pk déjà visités.

### 🟠 3.4. `RealEstateProgram.slug = SlugField(unique=True)` sans déduplication
`save()` slugifie le `name` mais ne gère pas les collisions. Deux programmes nommés "Bo Réflet" déclenchent une `IntegrityError` non capturée. À aligner sur `ParcelTag.save()` qui itère un suffixe `-2`.

### 🟠 3.5. `ProgramOrthophoto.save()` : race condition sur `is_current`
```python
super().save(*args, **kwargs)
if self.is_current:
    self.__class__.objects.filter(program=self.program).exclude(pk=self.pk).update(is_current=False)
```
Entre le `super().save()` et le `update()`, deux sauvegardes concurrentes peuvent toutes deux passer la `UniqueConstraint(condition=Q(is_current=True))`. À encapsuler dans une `transaction.atomic()` avec `select_for_update()`, ou inverser l'ordre (désactiver les autres avant d'activer celui-ci).

### 🟠 3.6. `Parcel.clean()` : `self.tags.exclude(...)` sur instance non sauvegardée
La protection `if self.pk:` évite l'erreur, mais à la première sauvegarde (juste après `pk` assigné), les tags ne sont pas encore liés (M2M se fait après `save()`). La validation est donc incomplète. À déplacer dans un signal `m2m_changed`.

### 🟠 3.7. `SaleBuyer.clean()` empêche plus d'un acheteur principal — mais permet zéro
Le modèle exige qu'il n'y ait jamais plus d'un `is_primary=True`, mais ne garantit pas qu'il y en ait au moins un. Le `__str__` de `SaleFile` peut donc afficher "Client" à la place du nom.

### 🟡 3.8. `PaymentInstallment.balance` toujours ≥ 0
Si `amount_paid > amount_due` (sur-paiement), le `save()` force `balance = 0` mais la `clean()` a déjà validé que `balance >= 0`. Aucun mécanisme pour détecter le sur-paiement → écart silencieux.

### 🟡 3.9. `__str__` qui chargent les FK
`Parcel.__str__` accède à `self.program.name`, `Reservation.__str__` à `self.customer`, etc. Sans `select_related` côté admin/listings = N+1.

### 🟡 3.10. Permission `view_patient_data` sur un modèle immobilier
Les permissions `Parcel.Meta.permissions` incluent `view_patient_data` ("Peut voir les données patient/client"). Vocabulaire médical hérité d'un autre projet — à renommer en `view_customer_data`.

### 🟢 3.11. `Customer.__str__` retourne `"Entreprise"` ou `"Client"` génériques quand le nom est vide
Indolore, mais brouille les exports/admin. Préférer un fallback avec ID (`f"Client #{self.pk}"`).

---

## 4. Vues & API (`parcelaire/views.py`, `parcelaire/api/views.py`)

### 🔴 4.1. `MapView`, `MapCommercialView`, `RealEstateMap3DView` — sans `LoginRequiredMixin`
```python
class MapView(TemplateView):
    template_name = "map.html"
class MapCommercialView(TemplateView):
    template_name = "mapcommercial.html"
class RealEstateMap3DView(TemplateView):
    template_name = "map_3d.html"
```
N'importe qui (anonyme) accède aux URLs `/map/`, `/map_commercial`, `/api/map/3d/`. Ces pages exposent toute la cartographie commerciale via l'API. **À encapsuler avec `LoginRequiredMixin` + `PermissionRequiredMixin('parcelaire.view_commercial_map')`**.

### 🔴 4.2. `RealEstateMapAPIView.permission_classes = [IsAuthenticatedOrReadOnly]`
GET est autorisé en anonyme. La pseudo-protection "données financières masquées" repose sur `user.has_perm(...)`, mais l'utilisateur anonyme n'a tout simplement aucune permission, donc ça affiche bien "Masqué" — sauf que :
- les **géométries**, **statuts commerciaux**, **noms de projets/programmes**, **photos**, **tags**, **valeurs hypothécaires** issues de `crm_summary` (ligne 1083) restent visibles
- les **clients masqués** sont remplacés par "Masqué" mais le simple fait qu'un lot soit "Réservé" au profit d'un client est divulgué

À durcir avec `IsAuthenticated` au minimum (et idéalement `DjangoModelPermissions`).

### 🟠 4.3. Fuite N+1 sur les orthophotos
Dans `_build_from_assets` et `_build_from_parcels`, pour chaque actif/parcelle on appelle :
```python
self.get_program_current_orthophoto_payload(parcel.program)
self.get_program_orthophotos_payload(parcel.program)
```
Ces helpers font `program.orthophotos.filter(is_active=True).order_by(...)`. Même si `program__orthophotos` est en `prefetch_related`, le `.filter().order_by()` casse le prefetch et relance un SELECT par parcelle. Sur 1 200 parcelles → **1 200 requêtes**.

Fix : préfetcher avec un `Prefetch("orthophotos", queryset=ProgramOrthophoto.objects.filter(is_active=True).order_by(...))` ou regrouper par programme avant de boucler.

### 🟠 4.4. Charge utile dupliquée — orthophotos répétées par parcelle
Le payload renvoie `"orthophotos": [...]` dans **chaque** asset. Pour un programme avec 800 lots et 5 orthophotos, on duplique 5×800 = 4 000 entrées identiques. Le JSON dépasse facilement 5–10 MB par requête. À sortir en `data.orthophotos_by_program`.

### 🟠 4.5. Filtres ignorés côté client
`templates/map.html` ligne 1239 :
```js
fetch("{% url 'api-map-assets' %}", { headers: {'X-Requested-With': ...}, credentials: 'same-origin' })
```
Aucun paramètre `program`, `project`, `bbox`, `status`, `search`, `tag`, `zoom`, `limit` n'est jamais envoyé. Le backend a beau implémenter `apply_common_filters_*`, ils sont inactifs. Conséquences :
- Le `MAX_LIMIT=2500` est silencieusement atteint sur les gros datasets : tronquage muet
- Pas de chargement progressif quand l'utilisateur zoome ou filtre

À refactor : faire passer `?program=...&bbox=...&zoom=...` selon l'état de l'UI Alpine.

### 🟠 4.6. `parcel_queryset` exclut les parcelles déjà associées à un actif via `id__in=asset_parcel_ids`
```python
asset_parcel_ids = list(asset_queryset.exclude(parcel_id__isnull=True).values_list("parcel_id", flat=True))
parcel_queryset = parcel_queryset.exclude(id__in=asset_parcel_ids)
```
La liste est matérialisée avant la coupe `[:limit]` côté assets. Si `asset_queryset` retourne >2500 lignes et qu'on coupe ensuite, certaines parcelles seront exclues alors que leur asset n'est même pas renvoyé. Résultat : trous dans la carte selon le tri.

### 🟠 4.7. `cluster_radius` & dataset sans pagination
Dans `_build_from_assets`/`_build_from_parcels`, après le `queryset[:params["limit"]]`, on calcule encore `total_ca += ...` sur les seules entrées limitées. Le résumé "CA potentiel" est donc faux quand les données dépassent la limite, sans avertissement.

### 🟡 4.8. `serialize_orthophoto.tiles_url` non absolu
La méthode renvoie l'URL telle quelle (`/media/...`). Si le frontend est servi depuis un sous-domaine (CDN), Leaflet ne pourra pas charger les tuiles. À résoudre via `request.build_absolute_uri(...)`.

### 🟡 4.9. `compute_asset_height` lit `asset.construction_progress`
Ligne 892 : `progress = getattr(asset, "construction_progress", 40) or 40`. `PropertyAsset` n'a aucun champ `construction_progress` ; `getattr` renvoie toujours 40, donc la hauteur "en construction" est figée.

### 🟡 4.10. `is_building_asset` se base sur `"r+"` dans le label
Mauvaise heuristique : un quelconque label contenant `"r+"` (ex. "OR+") déclenche le mode immeuble. Préférer un champ `category="BUILDING"` côté `AssetCategory`.

### 🟡 4.11. `get_status_ui_from_parcel_status` mappe `LITIGATION` et `BLOCKED` sur `"Réservés"`
Cliniquement faux. Un lot en litige ou bloqué n'est ni réservé ni vendu. À mapper sur une nouvelle statusKey "Bloqués/Litige" ou ajouter un filtre dédié.

### 🟢 4.12. Nombreux `try/except: pass` qui masquent les vraies erreurs
~25 `except Exception: pass` dans `api/views.py`. À remplacer au minimum par `logger.exception(...)`.

---

## 5. Cartographie côté template (`map.html`, `mapcommercial.html`, `map_3d.html`)

### 🔴 5.1. Attribution OpenStreetMap manquante
```js
this.tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; PARCELLAIRE KAYDAN GROUPE',
})
```
**Violation directe de la licence ODbL d'OpenStreetMap**. L'attribution `© OpenStreetMap contributors` (lien vers la licence) est obligatoire. À ajouter d'urgence.

### 🟠 5.2. URL d'image externe codée en dur dans les popups
```js
const firstImg = asset.images?.[0] || 'https://artemisconstruction-ci.com/assets/images/portfolio/symphonia/7.jpg';
```
Chaque parcelle sans photo charge cette image hébergée chez un tiers (`artemisconstruction-ci.com`) :
- fuite de Referer vers ce site à chaque ouverture de popup
- dépendance d'un service externe qu'on ne contrôle pas
- risque de remplacement malveillant du contenu de l'image

À remplacer par une image servie depuis `/static/`.

### 🟠 5.3. Risques d'injection HTML dans `buildPopup`
Plusieurs `${...}` ne sont pas passés par `escapeHtml` :
```js
<strong>${asset.price || '—'}</strong>
<strong>${asset.surface || '—'}</strong>
${asset.construction_stats?.valeur_hypothecaire || '—'}
${monthlyDelta} ... ${progress} ... ${ratioLabel}
```
Aujourd'hui les valeurs viennent de `money_display()` côté backend (string sûre), mais elles transitent ensuite par `metadata.crm_lot_sync` qui peut contenir du contenu issu de l'API CRM externe. Avec une CSP désactivée (cf. §1.5), un tag `<script>` glissé dans `cout_actif` exécuterait du JS dans la session. À durcir : appliquer `escapeHtml` partout, y compris `tag.color` (interpolé dans un attribut `style=`).

### 🟠 5.4. Aucune `LoginRequiredMixin` côté `MapCommercialView`
Le template `mapcommercial.html` (118 KB) est servi en accès anonyme — il fait `fetch('/api/map/assets/')` qui est aussi anonyme (cf. §4.2). Toute la cartographie commerciale est donc publique.

### 🟡 5.5. Coordonnées et zoom initiaux codés en dur
`setView([5.46771, -3.96454], 17)` cible Grand-Bassam. Si l'utilisateur n'a aucun programme dans cette zone, la carte s'ouvre vide. Calculer le centre depuis le `program.boundary` du premier programme actif.

### 🟡 5.6. `mapcommercial.html` (118 KB) et `map.html` (156 KB) dupliquent ~80% du JS
Beaucoup de fonctions sont copiées (popup, fetch, normalize). Toute correction doit être dupliquée. À factoriser dans un fichier static (`/static/js/map_core.js`).

### 🟢 5.7. `escapeHtml` non visible — implémentation à vérifier
`buildPopup` utilise `this.escapeHtml(...)`. À s'assurer que la méthode gère bien `'`, `"`, `>` et caractères Unicode.

---

## 6. Services CRM (`parcelaire/services/`)

### 🟠 6.1. `KaydanCRMLotSyncService` — `EXTERNAL_LOTS_API_*` lus à l'import
```python
class KaydanCRMLotSyncService:
    EXTERNAL_LOTS_API_URL = settings.EXTERNAL_LOTS_API_URL
    EXTERNAL_LOTS_API_KEY = settings.EXTERNAL_LOTS_API_KEY
    EXTERNAL_LOTS_API_USERNAME = settings.EXTERNAL_LOTS_API_USERNAME
    EXTERNAL_LOTS_API_PASSWORD = settings.EXTERNAL_LOTS_API_PASSWORD
```
Évalués au chargement du module. Si l'env var n'est pas définie au démarrage (ex. tâche Celery qui démarre avant que `.env` ne soit lu), `settings.EXTERNAL_LOTS_API_URL` est `None` → `session.auth = (None, None)`, requêtes silencieusement non authentifiées. À évaluer dans `__init__`.

### 🟠 6.2. `env_required` mort-né
La méthode `env_required(name)` est définie sans `self`, n'est jamais appelée et plante à l'import si on tentait. À retirer ou réécrire en classmethod.

### 🟡 6.3. `fetch_for_project` envoie `lots` en `data=` (form-encoded) au lieu de JSON
```python
payload = {"lots": json.dumps(lots), "codeProjet": code_projet}
response = self.session.post(self.EXTERNAL_LOTS_API_URL, data=payload, ...)
```
Le double encodage (JSON → form-encoded) suppose que l'API CRM le déserialise. À documenter dans `crm_lot_sync.py` ou aligner avec un envoi `json=`. Pas de retry par lot en cas de timeout par chunk.

### 🟡 6.4. `crm_sync.py` : `timezone.timedelta` n'existe pas
```python
limit = timezone.now() - timezone.timedelta(hours=hours)
```
`django.utils.timezone` ne ré-exporte pas `timedelta`. C'est `datetime.timedelta`. Erreur d'exécution à la première synchro stale. À corriger : `from datetime import timedelta`.

### 🟢 6.5. Logger non configuré
`logger = logging.getLogger(__name__)` sans `LOGGING` dans settings → les logs CRM se perdent.

---

## 7. Commandes de management

### 🔴 7.1. `import_parcellaire_geojson.py` — fichier entièrement commenté (621 lignes)
Le seul outil d'import GeoJSON connu est inutilisable (toutes les lignes commencent par `#`). Pourtant, le projet possède 6 fichiers GeoJSON dans `static/json_lots/` (Ahoue, BoCenter, BoReal, BoReflet, Callisto, Kotibe). Sans cette commande, l'import doit se faire à la main via l'admin. Restaurer le code et écrire un test minimal.

### 🟠 7.2. `update_boreflets_tags.py` — création de tag sans `program`
```python
tag = ParcelTag.objects.create(name=name, slug=slugify(name), color=..., is_active=True)
```
`ParcelTag.program` est un FK obligatoire (NOT NULL). L'appel lève `IntegrityError`. La recherche `ParcelTag.objects.filter(name=name).first()` ignore aussi le programme : un tag d'un autre programme est réutilisé à tort. À filtrer par `program=program` explicitement.

### 🟢 7.3. Incohérence sémantique
`PROGRAM_NAME = "Callisto BNETD"` mais la docstring dit "LES RESIDENCES BO REFLETS". Renommer.

---

## 8. URLs

### 🟠 8.1. Plusieurs URLs sans `/` final
```python
path("map_commercial", MapCommercialView.as_view(), ...)
path("blocks/edit/<int:pk>", ProgramBlockUpdateView.as_view(), ...)
```
Inconsistant avec `APPEND_SLASH` activé par défaut → redirection 301 sur GET, mais POST sera rejeté sans trailing slash. Aligner toutes les routes.

### 🟡 8.2. `home` route sans slash de fin
`path('home', HomeView.as_view(), name='home')` casse `{% url 'home' %}` quand on s'attend à `/home/`.

### 🟡 8.3. `urlpatterns` répète `static(...)`
```python
] + static(STATIC_URL, ...)
if settings.DEBUG:
    urlpatterns += static(STATIC_URL, ...)   # doublon
```
La déclaration est ajoutée deux fois quand `DEBUG=True`. Pas critique mais sale.

---

## 9. Divers

### 🟢 9.1. `requirements.txt` daté
- `Django==4.2.29` LTS — OK
- `celery==5.2.7` (très vieux, 2022) avec `kombu==5.2.4`, `billiard==3.6.4.0` — incompatible avec Python 3.11+ stables récents. La doc Celery recommande 5.4+ pour Django 4.2.
- `python-dateutil==2.8.1` (2020), à remonter

### 🟢 9.2. Fichiers volumineux
- `parcelaire/models.py` 1 925 lignes
- `parcelaire/admin.py` 1 470 lignes
- `parcelaire/api/views.py` 2 780 lignes
- `templates/map.html` 3 137 lignes (156 KB)

À découper en sous-modules (`models/places.py`, `models/programs.py`, `api/views/map.py`, `api/views/parcels.py`).

### 🟢 9.3. `celerybeat-schedule.db` committé
Fichier généré localement par Celery Beat — à ajouter au `.gitignore`.

### 🟢 9.4. `db.sqlite3` committé alors que la prod est PostGIS
Source de confusion ; à `.gitignore`.

### 🟢 9.5. Présence d'images JPG lourdes dans `static/`
`VILLA-4piecesJum.jpg` (1.1 MB) et `VILLA-6pieces.jpg` (1.7 MB) committées. Préférer un stockage media + référence URL.

---

## 10. Top 10 actions prioritaires

| # | Action | Criticité |
|---|---|---|
| 1 | Roter immédiatement DB password, CRM API key/credentials (compromis dans Git) | 🔴 |
| 2 | Mettre `DEBUG = False` dans `prod.py` ; corriger `ALLOWED_HOSTS` à partir d'env | 🔴 |
| 3 | Générer et committer les migrations `parcelaire` et `ai_construction` | 🔴 |
| 4 | Ajouter `LoginRequiredMixin` + permission sur `MapView`, `MapCommercialView`, `RealEstateMap3DView` | 🔴 |
| 5 | Passer l'API `/api/map/assets/` à `IsAuthenticated` + `DjangoModelPermissions` | 🔴 |
| 6 | Restaurer `import_parcellaire_geojson.py` (sortir le code des commentaires) | 🔴 |
| 7 | Réinjecter l'attribution OpenStreetMap dans la couche tuiles (ODbL) | 🟠 |
| 8 | Faire passer les filtres (program/bbox/zoom) à l'API et préfetcher correctement les orthophotos | 🟠 |
| 9 | Activer `csp.middleware.CSPMiddleware` et définir une politique CSP de base | 🟠 |
| 10 | Échapper systématiquement les variables JS dans `buildPopup()` et supprimer l'image fallback externe `artemisconstruction-ci.com` | 🟠 |

---

*Ce rapport a été généré à partir d'une revue statique du code. Une exécution effective (lancer les migrations, démarrer le serveur, exécuter `python manage.py check --deploy`) est recommandée pour confirmer chaque point côté runtime.*
