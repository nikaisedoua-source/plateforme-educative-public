# Frontend — Flutter Web

Interface française de la plateforme éducative : inscription et connexion des élèves, accueil sans contenu scolaire fictif, et configuration des référentiels par un compte administrateur. Le frontend communique uniquement avec FastAPI; il ne se connecte jamais directement à PostgreSQL.

## Démarrage local

Dans un premier terminal, préparer et lancer l’API depuis `backend/` en suivant son `README.md` : configurer `DATABASE_URL` et un `SECRET_KEY` aléatoire dans `.env`, appliquer `alembic upgrade head`, créer le premier administrateur avec `python -m app.cli create-admin --email admin@example.com`, puis lancer `uvicorn app.main:app --reload`.

Dans un second terminal :

```bash
export PATH="$HOME/flutter/bin:$PATH"  # si Flutter n’est pas déjà dans PATH
cd frontend
flutter pub get
flutter run -d web-server --web-hostname localhost --web-port 8080 \
  --dart-define=API_BASE_URL=http://localhost:8000
```

Ouvrir ensuite `http://localhost:8080`. Le backend doit autoriser cette origine dans `CORS_ORIGINS` (elle est présente dans `backend/.env.example`). Pour une autre URL d’API, remplacer la valeur de `API_BASE_URL` au lancement.

Les inscriptions publiques créent uniquement des comptes `student`. Le rôle administrateur n’est jamais sélectionnable dans l’interface : le serveur le vérifie et protège toutes les routes `/api/v1/admin/*`. Le jeton de connexion reste en mémoire dans le navigateur et disparaît à la déconnexion ou au rechargement.

## Vérification

```bash
cd frontend
flutter analyze
flutter test
flutter build web --dart-define=API_BASE_URL=http://localhost:8000
```

Le build écrit dans `frontend/build/web/`; il ne contient ni secrets ni données de production. Ne jamais publier une configuration qui pointe vers une base ou une API de développement.
