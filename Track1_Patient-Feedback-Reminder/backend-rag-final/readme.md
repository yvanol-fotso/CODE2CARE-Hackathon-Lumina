# API Hospitalière Intelligente (Code2Care Hackathon)

**NOTE IMPORTANTE** : Cette API est déployée sur Render et est disponible pour être consommée à l'adresse suivante : https://rag-system-8dri.onrender.com. Pour l'endpoint d'analyse de sentiment, par exemple, l'URL complète serait https://rag-system-8dri.onrender.com/api/sentiment.

---

Bienvenue dans l'API Hospitalière Intelligente, développée par l'équipe **Lumina** lors du Hackathon **CODE2CARE**. Cette API est une solution avancée conçue pour transformer la gestion des informations et l'analyse des retours patients dans les établissements de santé. Elle intègre un système de Récupération Augmentée de Génération (RAG) pour interroger des documents (PDF et Excel), une analyse de sentiment sophistiquée pour les retours patients, et une intégration WhatsApp pour une communication fluide.

## Table des matières

- [Fonctionnalités Clés](#fonctionnalités-clés)
- [Technologies Utilisées](#technologies-utilisées)
- [Installation](#installation)
- [Structure des Répertoires](#structure-des-répertoires)
- [Endpoints de l'API](#endpoints-de-lapi)
- [Gestion des Erreurs](#gestion-des-erreurs)
- [Auteurs](#auteurs)
- [Licence](#licence)

---

## Fonctionnalités Clés

### Recherche et Récupération Augmentée (RAG)
Interrogez intelligemment des documents PDF et des fichiers Excel (contenant des données d'employés par exemple) pour obtenir des réponses précises et contextuelles.

### Analyse de Sentiment Avancée
Évaluez les retours des patients avec une analyse de sentiment professionnelle, incluant la détection d'emojis/autocollants, l'identification de thèmes clés, l'évaluation de l'intensité émotionnelle, et la génération d'insights actionnables.

### Intégration WhatsApp
Envoyez et recevez des messages via Twilio WhatsApp, permettant aux patients de poser des questions et de fournir des retours directement via leur application de messagerie préférée.

### Gestion des Fichiers
Téléchargez et listez des documents PDF et Excel directement via l'API, qui seront ensuite indexés pour le système RAG.

### Cache Intelligent
Le système RAG met en cache les embeddings vectoriels et ne re-traite les fichiers que si des modifications sont détectées, garantissant efficacité et performance.

---

## Technologies Utilisées

- **Flask** : Micro-framework web pour la construction de l'API RESTful
- **Google Gemini 1.5 Flash** (via ChatGoogleGenerativeAI) : Modèle de langage puissant pour le traitement du langage naturel, l'analyse de sentiment et la génération de réponses
- **GoogleGenerativeAIEmbeddings** : Pour la création d'embeddings vectoriels
- **LangChain** : Framework pour le développement d'applications basées sur les modèles de langage, utilisé pour le système RAG (chaînes QA, diviseurs de texte)
- **FAISS** : Bibliothèque pour la recherche de similarité efficace et le clustering de vecteurs denses, utilisée comme base de données vectorielle
- **PyPDF2** : Pour l'extraction de texte à partir de documents PDF
- **Pandas** : Pour la manipulation et l'extraction de données à partir de fichiers Excel
- **Twilio** : Pour l'intégration des services de messagerie WhatsApp
- **python-dotenv** : Pour la gestion des variables d'environnement
- **logging** : Pour la journalisation des activités de l'application

---

## Installation

Suivez ces étapes pour configurer et exécuter l'API localement.

### Prérequis

- Python 3.8+
- pip (gestionnaire de paquets Python)

### Configuration des Variables d'Environnement

Créez un fichier `.env` à la racine de votre projet et ajoutez-y les variables suivantes :

```env
GOOGLE_API_KEY="VOTRE_CLE_API_GOOGLE_GEMINI"
TWILIO_ACCOUNT_SID="VOTRE_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN="VOTRE_TWILIO_AUTH_TOKEN"
TWILIO_WHATSAPP_NUMBER="whatsapp:+1234567890" # Votre numéro Twilio WhatsApp avec le préfixe 'whatsapp:'

# Répertoires pour les fichiers (créés s'ils n'existent pas)
PDF_DIRECTORY="pdfs"
EXCEL_DIRECTORY="excel_files"

# Configuration du serveur Flask (pour le développement)
FLASK_HOST="0.0.0.0"
FLASK_PORT=5000
FLASK_DEBUG="True" # Mettez à "False" en production
```

### Lancement de l'Application

#### Étape 1 : Cloner le dépôt

```bash
git clone https://github.com/votre_utilisateur/votre_repo.git
cd votre_repo
```

#### Étape 2 : Créer un environnement virtuel

```bash
python -m venv venv
# Sur Windows
.\venv\Scripts\activate
# Sur macOS/Linux
source venv/bin/activate
```

#### Étape 3 : Installer les dépendances

```bash
pip install -r requirements.txt
```

Si vous n'avez pas de requirements.txt, installez-les manuellement :

```bash
pip install Flask PyPDF2 pandas openpyxl twilio pydantic python-dotenv langchain-google-genai langchain_community faiss-cpu
```

#### Étape 4 : Placer vos fichiers

- Créez un dossier `pdfs` à la racine de votre projet et placez-y vos documents PDF
- Créez un dossier `excel_files` à la racine de votre projet et placez-y vos fichiers Excel (par exemple, des données d'employés ou des plannings)

#### Étape 5 : Exécuter l'application

```bash
python api2.py
```

L'API devrait démarrer et être accessible à http://0.0.0.0:5000 (ou le port que vous avez configuré). Lors du premier démarrage, l'API va traiter vos fichiers et créer un index FAISS. Cela peut prendre un certain temps en fonction du volume de vos documents.

---

## Structure des Répertoires

```
.
├── .env
├── api2.py
├── pdfs/
│   └── document1.pdf
│   └── rapport_medical.pdf
├── excel_files/
│   └── employees.xlsx
│   └── patient_data.xls
├── faiss_index_api/
│   ├── index.faiss
│   └── index.pkl
├── processed_files_metadata.json
├── README.md
└── requirements.txt
```

---

## Endpoints de l'API

Tous les endpoints renvoient une réponse JSON.

### 1. Health Check

Vérifie l'état de santé de l'API.

- **URL** : `/`
- **Méthode** : GET
- **Réponse Succès** : 200 OK

```json
{
    "status": "healthy",
    "service": "PDF RAG API with Excel Support & Sentiment Analysis",
    "timestamp": "2025-07-18T14:30:00.000000",
    "version": "2.0.0"
}
```

### 2. Interroger les Documents (RAG)

Permet d'interroger les documents PDF et Excel chargés et d'obtenir des réponses basées sur leur contenu.

- **URL** : `/api/query`
- **Méthode** : POST
- **Corps de la Requête** (JSON) :

```json
{
    "question": "Quel est le temps d'attente moyen au service d'urgence?"
}
```

- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "data": {
        "question": "Quel est le temps d'attente moyen au service d'urgence?",
        "answer": "Selon nos registres, le temps d'attente moyen au service d'urgence est d'environ 45 minutes.",
        "timestamp": "2025-07-18T14:35:00.000000",
        "processing_id": "20250718_143500_123456",
        "sources_used": 2,
        "pdf_sources": ["Rapport_Services_Urgence_Q2_2025.pdf"],
        "excel_sources": ["Data_Temps_Attente.xlsx"],
        "relevant_passages": [
            {
                "source": "Rapport_Services_Urgence_Q2_2025.pdf",
                "source_type": "pdf",
                "preview": "Le temps d'attente moyen au service d'urgence pour le deuxième trimestre 2025 était de 45 minutes..."
            },
            {
                "source": "Data_Temps_Attente.xlsx",
                "source_type": "excel",
                "preview": "SHEET: Urgence_Stats, Columns: Date, Patient_ID, Wait_Time_Min..."
            }
        ]
    }
}
```

**Réponses d'Erreur** :
- 400 Bad Request : Si la question est manquante ou vide
- 500 Internal Server Error : Si le service RAG n'est pas initialisé ou une erreur interne survient

### 3. Analyse de Sentiment des Retours Patients

Analyse en profondeur le sentiment d'un retour patient, en considérant le texte, les autocollants/emojis, l'âge du patient, le département, les temps d'attente, etc.

- **URL** : `/api/sentiment`
- **Méthode** : POST
- **Corps de la Requête** (JSON) :

```json
{
    "feedback_text": "Le personnel était très professionnel et l'hôpital était d'une propreté impeccable. 😊 Excellent service !",
    "patient_age": "30-40",
    "department": "Cardiology",
    "wait_time_min": 10,
    "resolution_time_min": 60,
    "rating": 5,
    "feedback_id": "FB001",
    "patient_id": "P001"
}
```

*Note : `feedback_id`, `patient_id`, `patient_age`, `department`, `wait_time_min`, `resolution_time_min`, `rating` sont facultatifs. Des valeurs par défaut sont appliquées s'ils sont absents.*

- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "data": {
        "feedback_id": "FB001",
        "patient_id": "P001",
        "analysis_timestamp": "2025-07-18T14:40:00.000000",
        "sticker_analysis": {
            "sticker_sentiment": "positive",
            "stickers_found": ["😊"],
            "sentiment_scores": {"positive": 1, "negative": 0, "neutral": 0}
        },
        "ai_analysis": {
            "primary_sentiment": "positive",
            "confidence_score": 95,
            "emotional_intensity": 8,
            "key_themes": ["professionalism", "cleanliness", "excellent_service"],
            "contextual_factors": "Patient jeune-adulte, département de cardiologie, faible temps d'attente.",
            "patient_behavior_analysis": "Le patient exprime une grande satisfaction, valorisant l'efficacité et la qualité du service. L'utilisation d'emojis positifs renforce le sentiment.",
            "actionable_insights": ["Maintenir les standards de professionnalisme", "Mettre en avant la propreté de l'établissement"],
            "urgency_level": 1,
            "sentiment_explanation": "Le feedback est clairement positif, avec des mentions spécifiques de 'professionnel' et 'propreté impeccable', ainsi qu'un emoji positif et une note élevée. Le faible temps d'attente contribue à cette satisfaction.",
            "department_specific_insights": "Pour la cardiologie, l'assurance et l'efficacité sont clés, ce qui est bien réflété ici."
        },
        "contextual_data": {
            "patient_age": "30-40",
            "department": "Cardiology",
            "wait_time_min": 10,
            "resolution_time_min": 60,
            "rating": 5
        },
        "risk_factors": {
            "risk_score": 0,
            "risk_level": "low",
            "risk_factors": []
        },
        "recommendations": ["Share positive feedback with staff", "Identify best practices to replicate"]
    }
}
```

**Réponses d'Erreur** :
- 400 Bad Request : Si `feedback_text` est manquant
- 500 Internal Server Error : Si le service RAG n'est pas initialisé ou une erreur interne survient

### 4. Envoyer un Message WhatsApp

Permet d'envoyer un message WhatsApp à un numéro spécifié.

- **URL** : `/api/whatsapp/send`
- **Méthode** : POST
- **Corps de la Requête** (JSON) :

```json
{
    "to": "+237699123456",
    "message": "Bonjour, votre rendez-vous est confirmé pour demain à 10h.",
    "media_url": "https://example.com/image.jpg"
}
```

*Note : `media_url` est facultatif.*

- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "data": {
        "success": true,
        "message_sid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "to": "whatsapp:+237699123456",
        "status": "queued",
        "timestamp": "2025-07-18T14:45:00.000000"
    }
}
```

**Réponses d'Erreur** :
- 400 Bad Request : Si 'to' ou 'message' sont manquants
- 500 Internal Server Error : Si le service WhatsApp n'est pas configuré ou une erreur interne survient

### 5. Webhook WhatsApp

Endpoint pour recevoir les messages entrants de WhatsApp via Twilio. Cette API répondra automatiquement aux messages des utilisateurs en utilisant le système RAG.

- **URL** : `/api/whatsapp/webhook`
- **Méthode** : POST
- **Paramètres de la Requête** (Form-data, envoyés par Twilio) :
  - `Body` : Contenu du message WhatsApp
  - `From` : Numéro de l'expéditeur (par exemple, whatsapp:+237699123456)

- **Réponse Succès** : 200 OK (réponse TwiML)

```xml
<Response>
    <Message>Votre message a été traité. Voici la réponse...</Message>
</Response>
```

*Note : Cet endpoint est destiné à être configuré dans le tableau de bord Twilio comme l'URL de webhook pour votre numéro WhatsApp.*

### 6. Obtenir le Statut d'un Message WhatsApp

Récupère le statut d'un message WhatsApp envoyé précédemment.

- **URL** : `/api/whatsapp/status/<message_sid>`
- **Méthode** : GET
- **Paramètres de l'URL** :
  - `message_sid` : Le SID (identifiant unique) du message Twilio

- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "data": {
        "sid": "SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "status": "delivered",
        "to": "whatsapp:+237699123456",
        "from": "whatsapp:+1234567890",
        "body": "Bonjour, votre rendez-vous est confirmé pour demain à 10h.",
        "date_created": "2025-07-18T14:45:00.000000",
        "date_updated": "2025-07-18T14:45:10.000000",
        "error_code": null,
        "error_message": null
    }
}
```

**Réponses d'Erreur** :
- 500 Internal Server Error : Si le service WhatsApp n'est pas configuré ou une erreur interne survient

### 7. Obtenir les Informations Système

Fournit des informations détaillées sur l'état du système, y compris les fichiers chargés, le statut du cache et l'état des services.

- **URL** : `/api/system/info`
- **Méthode** : GET
- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "data": {
        "status": "active",
        "cache_status": "enabled",
        "pdfs_loaded": 2,
        "excel_files_loaded": 1,
        "pdf_files": ["document1.pdf", "rapport_medical.pdf"],
        "excel_files": ["employees.xlsx"],
        "pdf_details": {
            "document1.pdf": {
                "path": "pdfs/document1.pdf",
                "chunk_count": 10,
                "source_type": "pdf",
                "processed_at": "2025-07-18T14:20:00.000000",
                "last_modified": 1678886400.0,
                "file_size": 102400
            }
        },
        "excel_details": {
            "employees.xlsx": {
                "path": "excel_files/employees.xlsx",
                "sheets": {"Sheet1": {"rows": 50, "columns": ["Name", "Department"], "non_empty_cells": 100}},
                "total_sheets": 1,
                "chunk_count": 5,
                "source_type": "excel",
                "processed_at": "2025-07-18T14:21:00.000000",
                "last_modified": 1678886500.0,
                "file_size": 51200
            }
        },
        "vector_store_ready": true,
        "chain_ready": true,
        "sentiment_analyzer_ready": true,
        "whatsapp_service_ready": true,
        "last_check": "2025-07-18T14:50:00.000000"
    }
}
```

**Réponses d'Erreur** :
- 500 Internal Server Error : Si le service RAG n'est pas initialisé ou une erreur interne survient

### 8. Recharger les Services

Force le rechargement de tous les services (RAG, WhatsApp), ce qui inclut le re-traitement de tous les fichiers si nécessaire. Utile après l'ajout ou la suppression manuelle de fichiers.

- **URL** : `/api/system/reload`
- **Méthode** : POST
- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "message": "System reloaded successfully",
    "timestamp": "2025-07-18T14:55:00.000000"
}
```

**Réponses d'Erreur** :
- 500 Internal Server Error : Si une erreur survient pendant le rechargement

### 9. Télécharger un Fichier

Permet de télécharger un fichier PDF ou Excel vers le serveur. Le fichier sera automatiquement traité et indexé par le système RAG après le téléchargement.

- **URL** : `/api/files/upload`
- **Méthode** : POST
- **Type de Contenu** : `multipart/form-data`
- **Champ du Fichier** : `file` (le fichier lui-même)

**Exemple** (avec curl) :

```bash
curl -X POST -F "file=@/path/to/your/new_document.pdf" http://localhost:5000/api/files/upload
```

- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "message": "File uploaded and processed successfully: new_document.pdf",
    "file_path": "pdfs/new_document.pdf"
}
```

**Réponses d'Erreur** :
- 400 Bad Request : Si aucun fichier n'est fourni ou si le type de fichier n'est pas autorisé
- 500 Internal Server Error : Si le téléchargement ou le traitement du fichier échoue

### 10. Lister les Fichiers Téléchargés

Affiche la liste de tous les fichiers PDF et Excel actuellement stockés sur le serveur et utilisés par le système.

- **URL** : `/api/files/list`
- **Méthode** : GET
- **Réponse Succès** : 200 OK

```json
{
    "success": true,
    "data": {
        "pdf_files": [
            {
                "name": "document1.pdf",
                "path": "pdfs/document1.pdf",
                "size": 102400,
                "modified": "2025-07-18T14:20:00.000000"
            }
        ],
        "excel_files": [
            {
                "name": "employees.xlsx",
                "path": "excel_files/employees.xlsx",
                "size": 51200,
                "modified": "2025-07-18T14:21:00.000000"
            }
        ]
    }
}
```

**Réponses d'Erreur** :
- 500 Internal Server Error : Si une erreur survient lors de la lecture des répertoires

---

## Gestion des Erreurs

L'API utilise des codes de statut HTTP standard et renvoie des messages d'erreur JSON pour faciliter l'intégration :

- **400 Bad Request** : La requête du client est mal formée ou incomplète
- **404 Not Found** : L'endpoint demandé n'existe pas
- **405 Method Not Allowed** : La méthode HTTP utilisée n'est pas supportée pour cet endpoint
- **500 Internal Server Error** : Une erreur inattendue est survenue côté serveur

---

## Auteurs

Projet développé par l'équipe **Lumina** – CODE2CARE Hackathon.

---

## Licence

Ce projet est sous licence [MIT]. Voir le fichier LICENSE pour plus de détails.