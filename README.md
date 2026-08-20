# RéclamPro — MVP gestion des réclamations

Application web pour la gestion des réclamations clients (banque / assurance, zone UEMOA).
MVP couvrant les exigences "Must Have" du cahier des charges : capture omnicanale, ID
réglementaire, workflow, SLA, journal d'audit immuable, dashboard, export registre BCEAO.

## Stack

| Couche | Choix |
|---|---|
| Backend | Python 3.11+ · FastAPI · SQLAlchemy |
| Base | SQLite (fichier `backend/reclamations.db`) |
| Auth | JWT HS256 (PyJWT) + bcrypt pour les mots de passe |
| Frontend | HTML + CSS + JavaScript (zéro build, zéro npm) |
| Auth | JWT HS256 (PyJWT) + bcrypt + **MFA TOTP** (pyotp + QR code) |
| Chiffrement | **AES-256 (Fernet)** sur email/téléphone/n° compte (NFR005) |
| Reports | openpyxl (Excel) + reportlab (PDF) — registre BCEAO formaté + rapport mensuel |
| Tests API | pytest (135 tests) — exécution par défaut |
| Tests E2E navigateur | pytest-playwright + Chromium (33 tests) — exécution sur demande |

## Démarrage rapide

### Option A — Docker (1 commande, PostgreSQL inclus)

```bash
cp .env.example .env       # adapter les secrets pour la prod
docker compose up --build
```

L'application démarre sur **http://localhost:8000** avec PostgreSQL 16, base seedée
automatiquement (admin/admin123 + agent/agent123 + 25 réclamations de démo).

Pour **arrêter** : `docker compose down` (les données restent dans le volume `db_data`).
Pour **réinitialiser** complètement : `docker compose down -v`.

### Option B — Python local (SQLite, sans Docker)

```powershell
# 1. Installer les dépendances Python
cd backend
python -m pip install -r requirements.txt

# 2. Initialiser la base avec des données de démo (6 agents, 7 clients, 25 réclamations)
python -m app.seed

# 3. Lancer le serveur
python -m uvicorn app.main:app --reload
```

Ouvrir http://127.0.0.1:8000 — la page de connexion s'affiche.

### Comptes de démo

| Identifiant | Mot de passe | Rôle | Droits |
|---|---|---|---|
| `admin` | `admin123` | ADMIN | Tout : créer, lire, commenter, changer statut, affecter, **clôturer**, **exporter le registre BCEAO**, **gérer les utilisateurs** |
| `agent` | `agent123` | AGENT | Créer, lire, commenter, changer statut, affecter (pas de clôture, ni d'export, ni de gestion utilisateurs) |

L'admin peut créer d'autres comptes via la page **Utilisateurs**, avec les rôles
`AGENT`, `GESTIONNAIRE`, `SUPERVISEUR`, `CONFORMITE` ou `ADMIN`.

### Pages

- **Portail client public** (sans login) : http://127.0.0.1:8000/portail.html — formulaire
  de soumission, retour avec n° dossier + lien de suivi (token)
- **Suivi client public** : http://127.0.0.1:8000/portail-suivi.html?token=… — barre de
  progression, statut, historique filtré (audit interne masqué)
- **Login** (avec MFA TOTP si activée) : http://127.0.0.1:8000/login.html
- **Sécurité MFA** : http://127.0.0.1:8000/mfa.html — activation par QR code (Google
  Authenticator / Authy), désactivation protégée par mot de passe
- **Dashboard** : http://127.0.0.1:8000/ — KPIs, donut conformité SLA, courbe d'évolution mensuelle,
  répartitions catégorie/canal/priorité, calendrier du jour, alertes SLA, volume hebdo
- **Liste réclamations** : http://127.0.0.1:8000/reclamations.html — filtres avancés
  (recherche texte, statut, priorité, catégorie, canal, équipe affectée, plage de dates, alerte SLA)
- **Détail dossier** : transitions de statut, affectation à un agent, **transfert vers une autre
  équipe avec motif obligatoire et notification automatique**, commentaires, clôture (admin)
- **Ma file** : http://127.0.0.1:8000/ma-file.html — espace personnel de chaque utilisateur,
  bilan **à traiter / en cours / traités / alerte SLA** + liste filtrable de ses dossiers
- **Notifications** : http://127.0.0.1:8000/notifications.html — badge live (rafraîchi toutes les 30 s)
  dans la topbar, marquage individuel ou en lot
- **Nouveau dossier** : http://127.0.0.1:8000/nouvelle.html
- **Reportings** (admin) : http://127.0.0.1:8000/reportings.html — pilotage de l'activité par période
  (semaine / mois / trimestre / année) et par dimension (catégorie, sous-catégorie, priorité, canal,
  équipe, statut, agent), série temporelle (jour/semaine/mois/année), contrôles de conformité SLA,
  **tableau Performance par équipe** (volumes à traiter / en cours / traités, alerte SLA, délai moyen
  — clic = drill-down) et **tableau Performance par agent** (même décomposition par agent affecté)
- **Utilisateurs** (admin) : http://127.0.0.1:8000/utilisateurs.html — créer, modifier rôle,
  réinitialiser mot de passe, activer/désactiver
- **Doc API Swagger** : http://127.0.0.1:8000/docs
- **Export registre** (admin) : http://127.0.0.1:8000/api/exports/registre.csv

## Lancer les tests

```powershell
cd backend

# Suite API rapide (135 tests, ~1 min)
python -m pytest -v

# Suite E2E navigateur (33 tests, ~2 min) — installation préalable :
python -m playwright install chromium
python -m pytest tests_e2e/ -v
```

**135 tests API** couvrent : génération d'ID (RG007), calcul SLA (RG001-004), workflow,
clôture motif obligatoire (RG008), validation > seuil (RG009), audit immuable (BR002),
auth + MFA + RBAC, exports CSV/Excel/PDF, rétention RGPD, multi-entité, IA, doublons,
notifications, templates, IMAP, WhatsApp, Power BI.

**33 tests E2E navigateur** (Playwright + Chromium) :
- Authentification (login OK/KO, logout, MFA, demo credentials)
- Portail public client (soumission, suivi via token, validation HTML5)
- Workflow agent (création + suggestion IA + commentaires + changement statut)
- Filtres avancés + pagination (URL state, navigation pages)
- Multi-langue FR/EN (persistance + traduction sidebar)
- Admin (utilisateurs, reportings, clôture complète, exports)

Les E2E démarrent un serveur dédié sur le port **8766** avec une base SQLite isolée
(`e2e_test.db`) qui est seedée automatiquement. Aucun conflit avec votre dev local.

Pour les exécuter en mode visuel (Chromium ouvert pour debug) :

```powershell
python -m pytest tests_e2e/ --headed --slowmo 500
```

## Déploiement

### Architecture conteneurisée

```
┌──────────────────┐      ┌──────────────────┐
│  reclampro-app   │─────▶│  reclampro-db    │
│  FastAPI         │      │  PostgreSQL 16   │
│  port 8000       │      │  port 5432       │
│  user: app (1000)│      │  volume db_data  │
│  volume uploads  │      │                  │
└──────────────────┘      └──────────────────┘
```

- **Image Docker** : multi-stage Python 3.12-slim, ~150 Mo, user non-root, healthcheck
  `/api/health` toutes les 30 s
- **Entrypoint** ([backend/docker-entrypoint.sh](backend/docker-entrypoint.sh)) :
  attend PostgreSQL, applique le schéma SQLAlchemy, seede si `SEED_AT_STARTUP=true` ET DB vide
- **Volumes persistants** : `db_data` (base PostgreSQL) + `app_uploads` (pièces jointes)
- **Réseau** : isolé via le réseau Docker par défaut (l'app voit `db` par DNS interne)

### Variables d'environnement clés

| Variable | Défaut | Description |
|---|---|---|
| `DATABASE_URL` | sqlite:///… | PostgreSQL en prod : `postgresql+psycopg://user:pwd@host:5432/db` |
| `JWT_SECRET` | dev-secret | **Obligatoire en prod** : `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `APP_CRYPTO_KEY` | dev-key | **Obligatoire en prod** : clé Fernet pour le chiffrement AES des données client |
| `SEED_AT_STARTUP` | true | Seede les comptes démo si DB vide (mettre `false` en prod !) |
| `EMAIL_DRIVER` | console | `smtp` pour l'envoi réel |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_TLS` / `SMTP_FROM` | — | Config SMTP |
| `WHATSAPP_DRIVER` | console | `cloud` pour Meta Business API |
| `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` / `WHATSAPP_VERIFY_TOKEN` | — | Config WhatsApp |
| `ARCHIVAGE_APRES_JOURS` | 1825 (5 ans) | Délai archivage automatique des clôtures |
| `ANONYMISATION_APRES_JOURS` | 3650 (10 ans) | Délai anonymisation RGPD |

### CI/CD GitHub Actions

[.github/workflows/ci.yml](.github/workflows/ci.yml) lance trois jobs sur chaque push :

1. **tests-api** — 135 tests pytest (~1 min)
2. **tests-e2e** — 33 tests Playwright + Chromium (~2 min) avec upload des traces en cas d'échec
3. **docker-build** — build de l'image + **smoke test** (démarre le conteneur et vérifie
   que `/api/health` répond 200 en moins de 30 s)

Cache `pip` et `docker buildx` activés pour des runs < 3 min.

### Passer à la production

Avant le premier déploiement réel :

1. **Générer des secrets forts** : `cp .env.example .env` puis remplacer
   `JWT_SECRET` et `APP_CRYPTO_KEY` par des chaînes aléatoires ≥ 32 caractères
2. **`SEED_AT_STARTUP=false`** pour ne pas créer les comptes démo
3. **Créer le premier admin** manuellement :
   `docker compose exec app python -c "from app.database import SessionLocal; from app import models; from app.services.auth import hasher_mot_de_passe; s=SessionLocal(); s.add(models.Agent(nom='Admin', prenom='Prod', email_pro='admin@banque.ci', role='ADMIN', username='admin_prod', password_hash=hasher_mot_de_passe('VOTRE_MDP'))); s.commit()"`
4. **Reverse proxy + HTTPS** : devant le port 8000, ajouter Nginx ou Traefik avec
   certificat Let's Encrypt
5. **Backups PostgreSQL** réguliers du volume `db_data` (pg_dump quotidien)
6. **Logs** : rediriger vers un agrégateur (Loki, Elastic, Datadog…)

## Structure du projet

```
Reclamation/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI + montage du frontend statique
│   │   ├── config.py            Paramètres (SLA, seuils, etc.)
│   │   ├── database.py          SQLAlchemy engine + session
│   │   ├── models.py            Tables : Client, Agent, Reclamation, Interaction…
│   │   ├── schemas.py           Modèles Pydantic (validation entrée/sortie)
│   │   ├── crud.py              Opérations base
│   │   ├── seed.py              Données de démo
│   │   ├── routers/             Endpoints HTTP (reclamations, dashboard, exports, agents)
│   │   └── services/            Logique métier isolée (id_generator, sla, workflow, audit)
│   ├── tests/                   pytest (26 tests)
│   └── requirements.txt
├── frontend/
│   ├── index.html               Dashboard
│   ├── reclamations.html        Liste avec filtres
│   ├── nouvelle.html            Formulaire de création
│   ├── detail.html              Vue 360° d'un dossier
│   └── assets/                  CSS + JS (api.js, layout.js + une page = un script)
├── docs/                        CDC, cahier de test, maquette dashboard
└── README.md
```

## Couverture fonctionnelle vs cahier des charges

### Tier 4 — IA, mobile & intégrations BI (ajoutés)

- **Classification IA** (FR011) : `POST /api/reclamations/suggerer-ia` — classifieur hybride
  rule-based (dictionnaires métier banque/assurance pondérés) + apprentissage par voisinage
  Jaccard sur les dossiers historiques. Retourne catégorie + priorité + score de confiance +
  voisins similaires + explication. **Aucune dépendance LLM externe**, fonctionne hors-ligne.
  Bouton « 🤖 Suggérer » dans le formulaire de nouvelle réclamation
- **Analyse cause racine** (BR010 + FR054) : `GET /api/reports/causes-racines?mois=6` —
  clustering hiérarchique single-link sur similarité Jaccard des descriptions. Retourne les
  grappes de récurrence avec mots-clés représentatifs, catégorie et priorité dominantes,
  premier/dernier occurrence — outil clé pour piloter les plans d'amélioration
- **WhatsApp Business** (FR003) : service [whatsapp.py](backend/app/services/whatsapp.py) avec
  drivers `console` (dev) / `cloud` (Meta API). Webhook `/api/whatsapp/webhook` :
  *handshake* GET (verify token) + POST réception messages → création auto de dossier classé
  par IA + accusé WhatsApp. Endpoint `/api/whatsapp/envoyer` pour réponses sortantes
- **Power BI / Tableau** (FR056) : trois endpoints admin
  `/api/bi/{reclamations,agregats-quotidiens,kpi-temps-reel}` — JSON aplati avec champs
  analytiques pré-calculés (année, mois, trimestre, semaine ISO, jour, SLA %, équipe).
  Branchement Power BI : Source > Web > URL avancée avec header `Authorization: Bearer …`
- **Multi-langue FR/EN** : [i18n.js](frontend/assets/js/i18n.js) — dictionnaire de
  traductions, sélecteur 🌐 FR/EN dans la sidebar, choix persisté en localStorage
- **PWA + mode offline** (NFR008/010) : `manifest.json` + service worker
  [sw.js](frontend/sw.js). Installation en application native (Chrome/Edge/Safari mobile).
  Le portail public fonctionne hors-ligne : les soumissions sont mises en file dans
  `localStorage` et rejouées automatiquement au retour de la connexion

### Tier 2 — Différenciateurs concurrentiels (ajoutés)

- **Pagination serveur** : query params `skip` / `limit` sur `GET /api/reclamations`, total renvoyé via `X-Total-Count`, UI avec sélecteur de taille + navigation page précédente/suivante
- **Templates de réponse** (FR024) : modèles paramétrables avec variables `{client.prenom}`, `{reclamation.code}`, `{reclamation.date_echeance_sla}`, etc. — bibliothèque seedée + CRUD admin + endpoint `/rendre` qui applique le template sur un dossier réel
- **Détection de doublons** (FR013) : endpoint `POST /api/reclamations/detecter-doublons` qui calcule un score (email exact + catégorie + sous-catégorie + similarité Jaccard du texte) sur les 7 derniers jours
- **Validation hiérarchique multi-niveaux** (FR025) : chaîne d'approbation paramétrable (ex. `GESTIONNAIRE → SUPERVISEUR → ADMIN`), endpoints `/approbations/initier`, `/approuver`, `/rejeter`. Passage automatique en `DECISION` quand tous les niveaux ont validé. Le rejet renvoie en `EN_COURS` avec motif obligatoire
- **Notifications temps réel SSE** : endpoint `GET /api/notifications/stream?token=…`, push d'événements `count` (compteur non lues) et `notification` (nouvelle notif) à chaque dossier transféré/affecté — sans polling
- **Capture email entrante (IMAP)** (FR002) : service `imap_capture.py` + endpoint admin `POST /api/admin/imap/traiter` qui lit la boîte `reclamations@…` configurée et crée un dossier par email non lu. Configurable via `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`

### Tier 3 — Conformité réglementaire renforcée (ajoutés)

- **Registre BCEAO formaté** (FR053) : trois endpoints `GET /api/exports/registre.{csv,xlsx,pdf}` — l'Excel a un en-tête institutionnel, des couleurs par priorité, panneaux figés et largeurs adaptées ; le PDF est paysage A4 imprimable avec mention réglementaire
- **Rapport mensuel auto-généré** (RG012) : `GET /api/exports/rapport-mensuel.pdf?annee=…&mois=…` produit un PDF de synthèse avec volumétrie, conformité SLA, top catégories, répartition canal, liste des SLA dépassés, ligne de signature responsable conformité
- **Archivage 10 ans + RGPD** (RG011) : endpoints `GET /api/admin/retention/candidats` (liste éligibles), `POST /api/admin/retention/appliquer` (archive à J+5 ans, anonymise à J+10 ans), `POST /api/admin/retention/{code}/anonymiser-rgpd` (droit à l'effacement à la demande). L'anonymisation préserve le code et les méta réglementaires
- **Multi-entité** (BR009 + NFR004) : modèle `Entite` (BANQUE / ASSURANCE / AUTRE), seed avec Banque SIB-CI et Assurance NSIA-CI. Chaque équipe et chaque dossier appartiennent à une entité. **Isolation appliquée sur GET /api/reclamations et GET /api/reclamations/{code}** : un non-admin ne voit que les dossiers de son entité (404 sinon). L'ADMIN voit tout

### Tier 1 — Bloquants production bancaire (ajoutés)

- **Pièces jointes** (FR022) : upload/download PDF, images, audio jusqu'à 10 Mo, checksum SHA-256, MIME-whitelist
- **Email réel** (RG006) : service `communication.py` avec driver `console` (dev) ou `smtp` (prod) + templates ACR / clôture, preuves d'envoi tracées dans le journal d'audit
- **MFA TOTP** (RFC 6238) : compatible Google Authenticator / Authy / 1Password, activation via QR code, désactivation protégée par mot de passe
- **Chiffrement AES-256** (NFR005) : email / téléphone / numéro de compte chiffrés en base via Fernet (cryptography), déchiffrement transparent à la lecture, déduplication par hash SHA-256 indexable
- **Portail client public** (FR004 + FR033) : soumission sans login, token opaque, page de suivi avec barre de progression, journal interne masqué
- **PostgreSQL ready** : le code est 100 % ORM, passer en prod = changer la variable `DATABASE_URL` (dé-commenter `psycopg[binary]` dans requirements.txt)

Pour la production, définir :

```
APP_CRYPTO_KEY=<chaîne aléatoire ≥ 32 caractères>
JWT_SECRET=<chaîne aléatoire ≥ 32 caractères>
EMAIL_DRIVER=smtp
SMTP_HOST=smtp.prod.ci ; SMTP_PORT=587 ; SMTP_USER=… ; SMTP_PASSWORD=… ; SMTP_TLS=true
SMTP_FROM=reclamations@banque.ci
DATABASE_URL=postgresql+psycopg://user:pwd@host:5432/reclampro
```

### Couverture CDC

✅ Implémenté dans le MVP :

- BR001 — dossier unique non duplicable, ID `RECB-AAAAMM-NNNNN`
- BR002 — traçabilité immuable (table `interactions` sans endpoint DELETE)
- BR003 / RG001-RG004 — SLA paramétrables, alerte à 80%, échu à 100%
- BR007 — calcul automatique de l'état d'alerte SLA
- BR008 / RG006 — accusé de réception simulé (entrée dans le journal à la création)
- FR010-FR012 — catégorisation et priorisation
- FR020-FR021 — workflow de statuts piloté par le système, journal immuable
- FR040 / RG008 — clôture impossible sans motif
- FR050-FR053 — dashboard riche (donut SLA, courbe évolution, calendrier, répartitions) + export CSV registre BCEAO/CIMA
- RG007 — ID strictement croissant, jamais recyclé
- RG009 — montant > 500 000 FCFA requiert passage par VALIDATION avant clôture
- NFR004 — RBAC simple : ADMIN vs AGENT, isolation des fonctions sensibles (clôture, export, gestion utilisateurs)
- Authentification JWT + bcrypt + écran de login + module admin de gestion des comptes

⏳ Reporté à v2 (Should / Could / Won't du CDC) :
- Intégrations réelles email/WhatsApp/SMS/LDAP
- Authentification + RBAC complet (multi-rôles, multi-entités BR009)
- Mode offline agence (NFR008)
- Pièces jointes (FR022) — modèle prêt, endpoints à ajouter
- Notifications client réelles (FR031, FR032)
- Conservation 10 ans + archivage (RG011)

## Notes pour un débutant

- **Modifier les délais SLA** : `backend/app/config.py`, dictionnaire `SLA_HEURES`.
- **Ajouter une catégorie ou un canal** : éditer les ensembles dans `backend/app/schemas.py`
  (`CANAUX`, `CATEGORIES`, `MOTIFS_CLOTURE`). Les `schemas` valident les payloads.
- **Ajouter une transition de statut** : enrichir `TRANSITIONS` dans `backend/app/services/workflow.py`.
- **Réinitialiser les données** : `python -m app.seed` supprime et reconstruit la base.
- **Passer à PostgreSQL** plus tard : seule la variable `DATABASE_URL` change
  (ex. `postgresql+psycopg://user:pwd@host:5432/db`) — le reste du code est identique.
