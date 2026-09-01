# AtelierFlow

AtelierFlow est une application Flask responsive de suivi d’atelier et de chantiers. Elle est conçue pour fonctionner à plusieurs depuis un navigateur : projets, discussion partagée, tâches, rapports, équipe, photos et documents.

## Comptes fournis

| Utilisateur | Code | Rôle |
|---|---:|---|
| Lucien | `000` | Responsable atelier |
| Arnaud | `111` | Chef de chantier |
| Justin | `222` | Direction |
| David | `333` | Menuisier |

Changez ces codes dans `INITIAL_USERS` avant un usage réel. Après la première création de la base, modifier la liste ne modifie pas automatiquement les comptes existants.

## Mise en ligne avec GitHub et Render

1. Décompressez le ZIP.
2. Dans votre dépôt GitHub, choisissez **Add file → Upload files**.
3. Déposez le contenu du dossier `AtelierFlow` (pas le ZIP lui-même), puis validez le commit.
4. Dans Render, choisissez **New → Blueprint** et sélectionnez le dépôt.
5. Render détecte `render.yaml`. Validez la création du service.
6. Attendez que le statut passe à **Live**, puis ouvrez l’adresse fournie.

Le plan gratuit de Render peut perdre les données locales lors d’un redéploiement. Pour un usage durable, ajoutez un disque persistant Render monté sur `/opt/render/project/src/data`, ou utilisez une offre avec stockage persistant. L’application est déjà configurée pour placer la base et les fichiers dans ce dossier.

## Démarrage sur un ordinateur

Avec Python 3.11 ou plus récent :

```bash
python -m venv .venv
pip install -r requirements.txt
python app.py
```

Ouvrez ensuite `http://localhost:8080`.

## Données et sécurité

- La base SQLite et les fichiers sont créés dans `data/`.
- Les codes sont stockés sous forme de hash, pas en clair.
- Les téléchargements exigent une connexion.
- Les fichiers sont limités à 20 Mo et à une liste de formats courants.
- Définissez toujours une variable `SECRET_KEY` aléatoire en production (Render le fait automatiquement).

## Limites de cette version

La discussion est partagée et s’actualise automatiquement toutes les quatre secondes. Ce n’est pas une messagerie WebSocket instantanée. SQLite convient à une petite équipe sur un seul service web ; pour une utilisation plus importante, migrez vers PostgreSQL et un stockage objet pour les fichiers.
