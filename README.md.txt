# PDF → Word Converter — Documentation complète

## Architecture

```
project/
├── index.html          ← Frontend (inchangé)
├── pr.js               ← Frontend JS (mis à jour → appels API réels)
├── pr_css.css          ← Styles (inchangé)
└── backend/
    ├── main.py         ← Serveur FastAPI (routes API)
    ├── database.py     ← Configuration SQLAlchemy + SQLite
    ├── models.py       ← Table `conversions` (ORM)
    ├── converter.py    ← Logique pdf2docx (+ fallback pdfminer)
    └── requirements.txt
```

---

## Installation

### 1. Prérequis

- Python 3.10+
- pip

### 2. Installer les dépendances

```bash
cd backend
pip install -r requirements.txt
```

> **Note** : `pdf2docx` installe automatiquement LibreOffice-headless sur certains systèmes.
> Si l'installation échoue, le fallback `pdfminer` sera utilisé (texte brut uniquement).

### 3. Lancer le serveur

```bash
cd backend
python main.py
```

Le serveur démarre sur **http://localhost:8000**

---

## API Reference

### POST `/api/convert`
Upload un PDF et démarre la conversion en arrière-plan.

**Body** : `multipart/form-data`  
- `file` : fichier PDF (max 50 MB)

**Réponse 202** :
```json
{
  "job_id":   "uuid-v4",
  "filename": "document.docx",
  "status":   "queued"
}
```

---

### GET `/api/status/{job_id}`
Interroge l'état d'un job.

**Réponse** :
```json
{
  "job_id":   "...",
  "status":   "queued | processing | done | error",
  "original_filename": "rapport.pdf",
  "output_filename":   "rapport.docx",
  "file_size_in":  204800,
  "file_size_out": 98304,
  "created_at":  "2026-01-01T10:00:00",
  "completed_at":"2026-01-01T10:00:05",
  "error": null
}
```

---

### GET `/api/download/{job_id}`
Télécharge le fichier `.docx` converti.

**Réponse** : binaire `.docx` (Content-Disposition: attachment)

---

### GET `/api/stats`
Tableau de bord des conversions.

**Réponse** :
```json
{
  "total": 42,
  "done": 39,
  "error": 3,
  "in_progress": 0,
  "success_rate": 92.9,
  "recent": [...]
}
```

---

### DELETE `/api/job/{job_id}`
Supprime un job et son fichier de sortie.

---

## Base de données

SQLite · fichier `backend/converter.db` (créé automatiquement au démarrage)

### Table `conversions`

| Colonne            | Type       | Description                         |
|--------------------|------------|-------------------------------------|
| `id`               | VARCHAR(36)| UUID du job (clé primaire)          |
| `original_filename`| VARCHAR    | Nom du PDF d'origine                |
| `output_filename`  | VARCHAR    | Nom du .docx généré                 |
| `file_size_in`     | BIGINT     | Taille du PDF (octets)              |
| `file_size_out`    | BIGINT     | Taille du .docx (octets)            |
| `status`           | VARCHAR(20)| queued / processing / done / error  |
| `created_at`       | DATETIME   | Horodatage de création              |
| `completed_at`     | DATETIME   | Horodatage de fin                   |
| `output_path`      | TEXT       | Chemin absolu du .docx              |
| `error_message`    | TEXT       | Message d'erreur si échec           |

---

## Déploiement en production

### Variables à modifier

Dans `pr.js` :
```js
const API = "https://votre-domaine.com";   // au lieu de localhost:8000
```

### Avec Gunicorn (recommandé)

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Avec Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

---

## Moteurs de conversion

| Moteur       | Qualité     | Nécessite         |
|--------------|-------------|-------------------|
| `pdf2docx`   | ⭐⭐⭐ Haute  | `pip install pdf2docx` |
| `pdfminer`   | ⭐ Basique   | `pip install pdfminer.six python-docx` |

Le système bascule automatiquement sur le fallback si `pdf2docx` n'est pas disponible.