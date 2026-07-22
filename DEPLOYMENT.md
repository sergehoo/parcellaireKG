# Déploiement en production — KAYDAN Parcellaire

Guide opérationnel pour mettre la plateforme en production de façon sûre.
Il complète l'audit de sécurité (voir la mémoire `security-audit`) : les
correctifs **code/config** sont déjà appliqués (voir §0) ; les actions
**strictement opérateur** (rotation des secrets, TLS, sauvegardes) restent à
votre charge et sont listées en §6.

> ⚠️ **À lire avant tout `docker compose up`.** Tant que les secrets exposés
> n'ont pas été rotés (§1) et que le `.env` de prod n'est pas rempli, ne
> déployez pas : l'application démarre en mode **prod** (`prod.py`, `DEBUG=False`)
> et refusera de fonctionner sans `SECRET_KEY`/base de données valides.

---

## 0. Ce qui est déjà durci dans le code (rappel)

| Correctif | Où | Effet |
|-----------|-----|-------|
| Prod forcée `DJANGO_ENV=prod` + `DEBUG=False` | `docker-compose.yml` (web/celery/beat) | La prod ne peut plus tourner sur `dev.py`/`DEBUG=True` par accident. |
| HTTPS/HSTS/cookies sécurisés | `settings/prod.py` | `SECURE_SSL_REDIRECT`, `SESSION/CSRF_COOKIE_SECURE`, HSTS 1 an+preload, `X_FRAME_OPTIONS=DENY`, nosniff. |
| `/media/` protégé | `parcelaireKG/urls.py` | Servi derrière `login_required` (tuiles, documents, médias de construction ne sont plus publics). |
| Bucket MinIO privé | `docker-compose.yml` (init) | `mc anonymous set none` : plus d'accès anonyme aux TIFF source. |
| Celery lit le broker depuis l'env | `settings/prod.py` | Worker/beat joignent le conteneur Redis (le code en dur `127.0.0.1` de `base.py` est surchargé). |
| E-mail piloté par l'env | `settings/prod.py` | SMTP configurable ; sans `EMAIL_HOST`, aucun envoi n'est tenté (backend « dummy »). |
| API : auth requise + throttling + docs gardées | `settings/base.py` | `IsAuthenticated` par défaut, Swagger/ReDoc non publics. |

`manage.py check --deploy` sur `prod.py` ne remonte **aucune** alerte de
sécurité réelle (voir §4).

---

## 1. Rotation des secrets — OBLIGATOIRE (action opérateur)

L'audit a identifié des secrets présents en clair dans l'historique / le `.env`.
**Ils sont considérés comme compromis et doivent être régénérés** avant la mise
en production. Je ne manipule aucun secret réel : à faire par vous.

À roter puis reporter dans le `.env` de prod :

- `SECRET_KEY` (Django) — en générer une neuve :
  ```bash
  python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
  ```
- `DB_PASSWORD` (PostgreSQL) — et mettre à jour le rôle en base.
- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (console + bucket).
- `EXTERNAL_LOTS_API_KEY` / `_USERNAME` / `_PASSWORD` (CRM).
- `SAP_CLIENT_SECRET` (si l'intégration SAP est activée).
- `EMAIL_HOST_PASSWORD` (compte SMTP dédié, jamais un compte personnel).

> Après rotation, purgez aussi tout secret encore présent dans l'historique git
> si le dépôt a été partagé (BFG / `git filter-repo`).

---

## 2. Configuration de l'environnement

```bash
cp .env.example .env
# éditer .env : renseigner TOUTES les valeurs, avec les secrets rotés (§1)
```

Points de vigilance dans le `.env` :

- `ALLOWED_HOSTS` = le(s) domaine(s) réel(s) de prod (sans schéma).
- `CSRF_TRUSTED_ORIGINS` = ces domaines **avec** `https://`.
- `DOMAIN` = domaine racine (sert à composer l'hôte S3 public).
- `EMAIL_HOST` = serveur SMTP (laisser vide désactive proprement l'envoi des
  rapports ; ils restent consultables/téléchargeables dans l'app).

Le `.env` réel n'est **jamais** committé (`.gitignore`). Seul `.env.example`
(sans secret) l'est.

---

## 3. Build, migrations et démarrage

Le service `parcelaireweb` exécute automatiquement `collectstatic` au démarrage,
puis `gunicorn`. Les **migrations ne sont pas automatiques** : à lancer à la main.

```bash
# 1) Construire les images
docker compose build

# 2) Démarrer la base et Redis d'abord (facultatif mais plus propre)
docker compose up -d parcelairedb redis

# 3) Appliquer les migrations (inclut l'app `accounts` : profils utilisateurs)
docker compose run --rm parcelaireweb python manage.py migrate

# 4) Démarrer toute la stack (web + celery + beat + minio + traefik)
docker compose up -d

# 5) Créer le premier compte administrateur
docker compose exec parcelaireweb python manage.py createsuperuser
```

Le front React est **déjà buildé et versionné** (`static/orthophotos-app/assets/`).
Pour le reconstruire après une évolution front :

```bash
cd frontend && npm ci && npm run build   # écrit index.js / index.css à noms fixes
```

---

## 4. Vérifications post-déploiement

```bash
# Aucune alerte de sécurité attendue (hors W009 si SECRET_KEY factice)
docker compose exec parcelaireweb python manage.py check --deploy

# Suite de tests (103 tests)
docker compose exec parcelaireweb python manage.py test
```

Contrôles manuels (smoke test) :

- [ ] `https://<domaine>/` redirige vers la connexion, puis charge le SPA `/app/`.
- [ ] Une requête anonyme sur `/api/...` renvoie **403** (auth requise).
- [ ] `/api/schema/swagger-ui/` et `/redoc/` renvoient **403** en anonyme, OK connecté.
- [ ] Une tuile `/media/tiles_ortho/...` renvoie **302/403** en anonyme.
- [ ] En connecté, la carte affiche les orthophotos (tuiles chargées).
- [ ] Un utilisateur **sans** `view_financial_data` voit « Masqué » sur les montants.
- [ ] Le certificat TLS est valide et HSTS présent (`curl -sI` → `Strict-Transport-Security`).

---

## 5. Exploitation courante

- **Logs** : `docker compose logs -f parcelaireweb` (gunicorn), `... parcelairecelery`.
- **Régénération des alertes** : bouton dans le SPA (chemin async Celery, repli
  synchrone si le broker est indisponible) ou tâche `beat` planifiée.
- **Rapports e-mail** : nécessitent `EMAIL_HOST` configuré + destinataires actifs.
- **Mise à jour applicative** : `git pull` → `docker compose build` →
  `docker compose run --rm parcelaireweb python manage.py migrate` →
  `docker compose up -d`.

---

## 6. Durcissements recommandés (à décider par l'opérateur)

Ces points ne sont pas bloquants mais fortement conseillés en prod :

1. **Bind-mount source `.:/app`** (docker-compose, service web) : en prod, il
   masque les artefacts de l'image par le code de l'hôte. Prévoir un
   `docker-compose.prod.yml` (override) **sans** cette ligne pour garantir que
   l'image buildée est utilisée telle quelle.
2. **Ports exposés sur l'hôte** : Postgres (`5437:5432`) et Adminer (`8081:8080`)
   sont publiés. En prod, ne pas les exposer publiquement (les retirer ou les
   binder sur `127.0.0.1` + tunnel SSH). Adminer devrait être désactivé en prod.
3. **Sauvegardes** : `pg_dump` planifié de PostgreSQL + snapshot du volume
   MinIO ; tester la restauration.
4. **TLS** : Traefik doit servir HTTPS (Let's Encrypt) ; vérifier le
   renouvellement automatique.
5. **Surveillance** : agréger les logs (erreurs 5xx, échecs Celery) et alerter.
6. **Comptes & rôles** : créer les groupes de permissions
   (`view_financial_data`, `view_patient_data`, …) et n'attribuer les données
   sensibles qu'aux rôles habilités.

---

## 7. Rollback

```bash
git checkout <tag-ou-commit-précédent>
docker compose build
docker compose run --rm parcelaireweb python manage.py migrate   # si migration réversible
docker compose up -d
```

Conservez toujours une sauvegarde base + MinIO **avant** chaque déploiement pour
permettre un retour arrière complet.
