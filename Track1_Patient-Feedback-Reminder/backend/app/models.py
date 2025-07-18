from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, date

# --- Modèles d'entrée Payloads de requêtes ---

class FeedbackIn(BaseModel):
    """
    Modèle pour la création d'un nouveau feedback.
    Utilisé pour les données entrantes dans la requête POST /feedback
    et le nouvel endpoint POST /feedback_and_analyze.
    Maintenant inclut les champs contextuels pour l'API AI.
    """
    patient_id: str = Field(..., min_length=1, max_length=50, example="P001")
    text: str = Field(..., min_length=5, example="Le personnel était très attentif.")
    note: int = Field(..., ge=1, le=5, example=5)
    emoji: Optional[str] = Field(None, example="😀")

    patient_age: Optional[float] = Field(None, example=80.0, description="Âge du patient.")
    patient_gender: Optional[str] = Field(None, example="M", description="Genre du patient (M/F/Autre).")
    department: Optional[str] = Field(None, example="Radiology", description="Département concerné par le feedback.")
    wait_time_min: Optional[float] = Field(None, example=39.0, description="Temps d'attente en minutes.")
    resolution_time_min: Optional[float] = Field(None, example=129.0, description="Temps de résolution en minutes.")


class ExternalAIAnalysisDetails(BaseModel):
    """Corresponds to the 'ai_analysis' object within the AI service's response."""
    actionable_insights: Optional[List[str]] = None
    confidence_score: Optional[float] = None
    contextual_factors: Optional[str] = None
    department_specific_insights: Optional[str] = None
    emotional_intensity: Optional[int] = None
    key_themes: Optional[List[str]] = None
    patient_behavior_analysis: Optional[str] = None
    primary_sentiment: Optional[str] = None
    sentiment_explanation: Optional[str] = None
    urgency_level: Optional[int] = None
    personalized_message_draft: Optional[str] = None

    class Config:
        extra = "allow"

class ExternalAIContextualData(BaseModel):
    """Corresponds to the 'contextual_data' object within the AI service's response."""
    department: Optional[str] = None
    patient_age: Optional[float] = None
    rating: Optional[float] = None
    resolution_time_min: Optional[float] = None
    wait_time_min: Optional[float] = None

class ExternalAIRiskFactors(BaseModel):
    """Corresponds to the 'risk_factors' object within the AI service's response."""
    risk_factors: Optional[List[str]] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None

class ExternalAIStickerAnalysis(BaseModel):
    """Corresponds to the 'sticker_analysis' object within the AI service's response."""
    sentiment_scores: Optional[Dict[str, int]] = None
    sticker_sentiment: Optional[str] = None
    stickers_found: Optional[List[Any]] = None

class ExternalAIDataContent(BaseModel):
    """Corresponds to the 'data' object within the AI service's overall response."""
    ai_analysis: ExternalAIAnalysisDetails
    analysis_timestamp: datetime
    contextual_data: Optional[ExternalAIContextualData] = None
    feedback_id: Optional[str] = None
    patient_id: Optional[str] = None
    recommendations: Optional[List[str]] = None 
    risk_factors: Optional[ExternalAIRiskFactors] = None
    sticker_analysis: Optional[ExternalAIStickerAnalysis] = None

    class Config:
        extra = "allow"

class ExternalAIOverallResponse(BaseModel):
    """Corresponds to the top-level structure of the AI service's response."""
    data: ExternalAIDataContent
    success: bool

# --- Modèles d'entrée Payloads de requêtes pour notre API pour stockage DB ---

class AnalysisDataIn(BaseModel):
    """
    Modèle pour les données d'analyse IA spécifiques,
    qui seront stockées dans la colonne 'analysis' (JSONB) de notre DB.
    Ceci inclura toutes les données pertinentes de 'ai_analysis' de l'API externe,
    ainsi que d'autres champs si nous voulons les consolider dans la colonne 'analysis'.
    """
    primary_sentiment: Optional[str] = None
    confidence_score: Optional[float] = None
    actionable_insights: Optional[List[str]] = None
    keywords: Optional[List[str]] = None 
    personalized_message_draft: Optional[str] = None
    contextual_factors: Optional[str] = None
    department_specific_insights: Optional[str] = None
    emotional_intensity: Optional[int] = None
    key_themes: Optional[List[str]] = None 
    patient_behavior_analysis: Optional[str] = None
    sentiment_explanation: Optional[str] = None
    urgency_level: Optional[int] = None
    contextual_data: Optional[ExternalAIContextualData] = None
    risk_factors: Optional[ExternalAIRiskFactors] = None
    sticker_analysis: Optional[ExternalAIStickerAnalysis] = None

    class Config:
        extra = "allow"

class AnalysisIn(BaseModel):
    """
    Modèle pour l'enregistrement d'une nouvelle analyse IA dans notre DB.
    Combine les données d'analyse générique et les recommandations spécifiques.
    """
    analysis: AnalysisDataIn
    recommendations: Optional[List[str]] = None

class RecallRequestIn(BaseModel):
    """
    Modèle pour la création d'une nouvelle demande de rappel/rendez-vous par le patient.
    """
    patient_id: str = Field(..., min_length=1, max_length=50, example="P001")
    request_object: str = Field(..., example="Demande de suivi pour le traitement X")
    requested_date: Optional[date] = Field(None, example="2025-08-15", description="Date souhaitée par le patient pour le rappel.")

class PersonalizedMessageIn(BaseModel):
    """
    Modèle pour l'envoi d'un message personnalisé (souvent généré ou validé par l'IA,
    puis potentiellement ajusté par un médecin).
    """
    recall_request_id: Optional[int] = Field(None, example=1, description="ID de la demande de rappel associée, si applicable.")
    patient_id: str = Field(..., min_length=1, max_length=50, example="P001")
    message_content: str = Field(..., example="Bonjour [Nom Patient], suite à votre demande de rappel, nous vous proposons un rendez-vous le 15/08/2025 à 10h. Cordialement, [Nom Médecin].")
    sent_by: str = Field(..., example="Dr. Dupont", description="Identifiant ou nom de l'expéditeur du message (médecin, système IA).")
    ai_message_analysis: Optional[Dict[str, Any]] = Field(None, example={"reasoning": "Based on positive sentiment."})


# --- Modèles de sortie (Réponses de l'API) pour notre API ---

class FeedbackOut(BaseModel):
    """
    Modèle pour la sortie d'un feedback patient.
    Utilisé pour les réponses des requêtes GET /feedback/{id} et LIST /feedbacks.
    """
    id: int = Field(..., example=1)
    patient_id: str = Field(..., example="P001")
    text: str = Field(..., example="Service rapide et efficace.")
    note: int = Field(..., example=4)
    emoji: Optional[str] = Field(None, example="👍")
    timestamp: datetime = Field(..., example=datetime.now())

    class Config:
        from_attributes = True

class AnalysisDataOut(BaseModel):
    """
    Modèle pour les données d'analyse IA contenues dans AnalysisOut.
    Ceci reflète la structure de la colonne 'analysis' (JSONB) de notre DB.
    """
    primary_sentiment: Optional[str] = None
    confidence_score: Optional[float] = None
    actionable_insights: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    personalized_message_draft: Optional[str] = None
    contextual_factors: Optional[str] = None
    department_specific_insights: Optional[str] = None
    emotional_intensity: Optional[int] = None
    key_themes: Optional[List[str]] = None
    patient_behavior_analysis: Optional[str] = None
    sentiment_explanation: Optional[str] = None
    urgency_level: Optional[int] = None
    contextual_data: Optional[ExternalAIContextualData] = None
    risk_factors: Optional[ExternalAIRiskFactors] = None
    sticker_analysis: Optional[ExternalAIStickerAnalysis] = None

    class Config:
        extra = "allow"

class AnalysisOut(BaseModel):
    """
    Modèle pour la sortie d'une analyse API IA.
    """
    feedback_id: int
    analysis: AnalysisDataOut
    recommendations: Optional[List[str]] = None
    analysis_timestamp: datetime

    class Config:
        from_attributes = True

class FeedbackAndAnalysisResponse(BaseModel):
    """
    Modèle de réponse combinée pour l'endpoint POST /feedback_and_analyze.
    """
    feedback: FeedbackOut
    analysis: AnalysisOut


class RecommendationOut(BaseModel):
    """
    Modèle pour la sortie d'une recommandation extraite.
    """
    feedback_id: int = Field(..., example=1)
    recommendation: str = Field(..., example="Former le personnel à l'accueil.")
    timestamp: datetime = Field(..., example=datetime.now())

    class Config:
        from_attributes = True

class RecallRequestOut(BaseModel):
    """
    Modèle pour la sortie d'une demande de rappel/rendez-vous.
    """
    id: int = Field(..., example=1)
    patient_id: str = Field(..., example="P001")
    request_object: str = Field(..., example="Demande de suivi pour le traitement X")
    requested_date: Optional[date] = Field(None, example="2025-08-15")
    request_timestamp: datetime = Field(..., example=datetime.now())
    status: str = Field(..., example="pending")
    approved_by: Optional[str] = Field(None, example="Dr. Smith")
    approval_date: Optional[datetime] = Field(None, example=datetime.now())

    class Config:
        from_attributes = True

class PersonalizedMessageOut(BaseModel):
    """
    Modèle pour la sortie d'un message personnalisé.
    """
    id: int = Field(..., example=1)
    recall_request_id: Optional[int] = Field(None, example=1)
    patient_id: str = Field(..., example="P001")
    message_content: str = Field(..., example="Bonjour [Nom Patient], ...")
    sent_by: str = Field(..., example="Dr. Dupont")
    sent_timestamp: datetime = Field(..., example=datetime.now())
    ai_message_analysis: Optional[Dict[str, Any]] = Field(None, example={"reasoning": "Based on positive sentiment."})

    class Config:
        from_attributes = True
