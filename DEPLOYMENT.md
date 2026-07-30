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
(sans secret) l'est. Dans Dockploy, collez ces variables dans l'onglet
**Environment** du service Compose ; Dockploy génère le `.env` utilisé par
`docker-compose.yml`.

---

## 3. Déploiement avec Dockploy

Le service `parcelaireweb` exécute automatiquement, au démarrage :
`migrate --noinput` → `collectstatic --noinput` → `gunicorn`. Les services
applicatifs attendent en outre que Postgres et Redis soient **sains**
(`healthcheck` + `depends_on: condition: service_healthy`), donc `migrate` ne
tourne jamais avant que la base accepte les connexions.

Dans Dockploy :

1. Créer un service **Compose** avec le type **Docker Compose** (pas
   « Docker Stack », car le fichier construit les images avec `build`).
2. Sélectionner le dépôt et définir **Compose Path** sur
   `./docker-compose.yml`.
3. Activer **Isolated Deployments** et renseigner les variables de
   `.env.example` dans l'onglet **Environment**.
4. Dans **Domains**, créer les routes HTTPS suivantes :

   | Usage | Service | Port conteneur |
   |-------|---------|----------------|
   | Application React | `frontend` | `80` |
   | API S3 publique | `parcelaire-orthos3` | `9000` |
   | Console MinIO | `parcelaire-orthos3` | `9001` |

   Les hôtes S3 et console doivent correspondre à `MINIO_S3_HOST` et
   `MINIO_CONSOLE_HOST`. Dockploy ajoute automatiquement les réseaux et labels
   de routage ; aucun label Traefik n'est défini dans le projet. Ne créez pas
   de domaine pour `parcelaireweb` : ce backend reste privé et le Nginx du
   service `frontend` lui transmet `/api`, `/accounts`, `/admin`, `/media` et
   les autres routes serveur.
5. Vérifier **Preview Compose**, puis lancer **Deploy**. Toute modification
   d'un domaine Compose nécessite ensuite un nouveau déploiement.

Après le premier déploiement, ouvrir le terminal du service `parcelaireweb`
dans Dockploy et exécuter :

```bash
python manage.py createsuperuser
```

PostgreSQL, Redis, les médias et MinIO utilisent des volumes Docker nommés.
Ils ne publient aucun port sur l'hôte et peuvent être sauvegardés via les
sauvegardes de volumes Dockploy.

Le frontend React est construit automatiquement par son image Docker à chaque
déploiement. Pour le lancer en développement avec le rechargement à chaud :

```bash
cd frontend
npm ci
npm run dev
```

---

## 4. Vérifications post-déploiement

```bash
# Aucune alerte de sécurité attendue (hors W009 si SECRET_KEY factice)
docker compose exec parcelaireweb python manage.py check --deploy

# Suite de tests complète
docker compose exec parcelaireweb python manage.py test
```

Contrôles manuels (smoke test) :

- [ ] `https://<domaine>/` redirige vers la connexion, puis charge le SPA React à la racine.
- [ ] Une requête anonyme sur `/api/...` renvoie **403** (auth requise).
- [ ] `/api/schema/swagger-ui/` et `/redoc/` renvoient **403** en anonyme, OK connecté.
- [ ] Une tuile `/media/tiles_ortho/...` renvoie **302/403** en anonyme.
- [ ] En connecté, la carte affiche les orthophotos (tuiles chargées).
- [ ] Un utilisateur **sans** `view_financial_data` voit « Masqué » sur les montants.
- [ ] Le certificat TLS est valide et HSTS présent (`curl -sI` → `Strict-Transport-Security`).

---

## 5. Exploitation courante

- **Logs** : onglet **Logs** de Dockploy (`frontend`, `parcelaireweb`,
  `parcelairecelery`, `parcelairebeat`).
- **Régénération des alertes** : bouton dans le SPA (chemin async Celery, repli
  synchrone si le broker est indisponible) ou tâche `beat` planifiée.
- **Rapports e-mail** : nécessitent `EMAIL_HOST` configuré + destinataires actifs.
- **Mise à jour applicative** : relancer **Deploy** dans Dockploy, ou utiliser
  son webhook après un push. Les migrations tournent automatiquement au
  démarrage du service web.

---

## 6. Durcissements recommandés (à décider par l'opérateur)

Ces points ne sont pas bloquants mais fortement conseillés en prod. Le compose
principal n'utilise déjà plus de bind-mount de code, ne publie ni PostgreSQL ni
Redis et n'embarque plus Adminer :

1. **Médias privés suivis par git** : ~34 500 fichiers sous `media/` (imagerie
   cadastrale, photos de chantier) sont traqués malgré `.gitignore` (committés
   avant la règle). Arrêter le suivi (les fichiers restent sur le disque) :
   ```bash
   git rm -r --cached media/ && git commit -m "Retire media/ du suivi git (données privées)"
   ```
   Si le remote a déjà reçu ces objets sur un dépôt public → purge d'historique
   nécessaire en plus (action opérateur, cf. §1).
2. **Sauvegardes** : activer dans Dockploy les sauvegardes des volumes
   PostgreSQL, `media_data` et MinIO ; tester la restauration.
3. **TLS** : activer HTTPS pour les trois domaines Dockploy et vérifier le
   renouvellement automatique des certificats.
4. **Surveillance** : agréger les logs (erreurs 5xx, échecs Celery) et alerter.
5. **Comptes & rôles** : créer les groupes de permissions
   (`view_financial_data`, `view_patient_data`, …) et n'attribuer les données
   sensibles qu'aux rôles habilités.
6. **Contrôle d'accès `/media/` par objet** : aujourd'hui tout compte
   authentifié peut lire n'importe quel fichier `media/` (documents de vente,
   pièces d'identité) en devinant le chemin. À terme : URLs signées à durée
   limitée ou vue à contrôle par objet/rôle sur les répertoires sensibles.
7. **CSP `script-src`** : contient encore `'unsafe-inline'` et `'unsafe-eval'`
    (requis par Alpine.js v3 sur les pages legacy). Migrer vers une CSP à nonces
    + Alpine `@alpinejs/csp` (ou décommissionner les pages HTML legacy) pour les
    retirer.
8. **Subresource Integrity** : les gabarits HTML legacy (`base.html`, `map.html`,
    `index.html`…) chargent Alpine/Leaflet depuis un CDN sans `integrity` et avec
    une version Alpine flottante (`3.x.x`). Self-héberger/bundler (comme la SPA)
    ou figer les versions + ajouter les hash SRI.

> Un audit de sécurité complet (`ostack security` + revue de code adversariale
> OWASP) a été réalisé le 2026-07-24 : les 5 failles HIGH et la plupart des MED
> ont été corrigées ; les points ci-dessus sont les résidus
> connus (non bloquants), suivis en tâches de fond.

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

---

## 8. Copilote IA (`ai_copilot`) — activation

> Livré sur la branche `feat/ai-copilot`. **Ne pas activer en prod sans revue.**
> Sans aucune clé LLM, `/api/copilot/chat/` renvoie **503** et le reste de
> l'application fonctionne normalement.

**8.1 Fournir au moins une clé LLM** (dans `.env`, cf. `.env.example`) :

```bash
DEEPSEEK_API_KEY=sk-...          # moteur par défaut
# facultatifs (activent ChatGPT / Claude dans le sélecteur du panneau) :
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
COPILOT_PROVIDER_PRIORITY=deepseek,openai,anthropic   # ordre du mode « Auto »
```

**8.2 Dépendances & migrations** (automatiques au déploiement, sinon manuel) :

```bash
docker compose exec parcelaireweb pip install -r requirements.txt   # openpyxl, python-docx, lxml
docker compose exec parcelaireweb python manage.py migrate ai_copilot   # 0001 → 0003
```

**8.3 Agent SQL (lecture seule)** — désactivé par défaut (superusers uniquement).
Pour habiliter un profil, attribuer la permission `ai_copilot.use_sql_agent`
(admin Django → Utilisateurs/Groupes, ou shell). L'accès aux tables
client/vente/paiement exige **en plus** `view_financial_data` **et**
`view_patient_data`.

**8.4 Confidentialité** — les données PII/financières sont **masquées avant
envoi** au LLM selon les droits de l'utilisateur. ⚠️ Pour un utilisateur
**habilité**, l'agent SQL peut renvoyer des lignes réelles à un LLM **tiers**
(DeepSeek par défaut) : valider la base légale et privilégier un fournisseur
sans rétention/entraînement (décision opérateur).

**8.5 Smoke test** :

- [ ] `GET /api/copilot/engines/` (connecté) liste ≥ 1 moteur ; `[]` ⇒ aucune clé.
- [ ] Un message simple renvoie une réponse ; le panneau ✨ apparaît sur toutes les pages.
- [ ] Un compte **sans** `view_patient_data` ne voit **aucun nom de client** dans une analyse du tableau de bord.
- [ ] Une action « relance orthophoto » demande une **confirmation** avant exécution.

**8.6 Diagnostic « Copilote muet »** :

| Symptôme | Cause probable |
|----------|----------------|
| HTTP **503** | Aucune clé LLM configurée (`engines/` renvoie `[]`). |
| HTTP **502** | Fournisseur LLM injoignable / clé invalide / quota fournisseur. |
| HTTP **429** | Débit dépassé (throttle `copilot` = 120/h par utilisateur). |
