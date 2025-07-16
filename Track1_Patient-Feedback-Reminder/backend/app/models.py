from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime 

# --- Modèles d'entrée Payloads de requêtes ---

class FeedbackIn(BaseModel):
    """
    Modèle pour la création d'un nouveau feedback.
    Utilisé pour les données entrantes dans la requête POST /feedback.
    """
    patient_id: str = Field(..., min_length=1, max_length=50, example="P001")
    text: str = Field(..., min_length=5, example="Le personnel était très attentif.")
    note: int = Field(..., ge=1, le=5, example=5) 
    emoji: Optional[str] = Field(None, example="😀") 


class AnalysisIn(BaseModel):
    """
    Modèle pour l'enregistrement d'une nouvelle analyse IA.
    Utilisé pour les données entrantes dans la requête POST /feedback/{id}/analyze.
    """
    analysis: Dict[str, Any] = Field(
        ...,
        example={
            "primary_sentiment": "positive",
            "confidence_score": 98.5,
            "actionable_insights": ["Améliorer la salle d'attente"],
            "keywords": ["personnel", "attentif", "efficace"]
        }
    )

# --- Modèles de sortie Réponses de l'API ---

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
    """
    primary_sentiment: Optional[str] = None
    confidence_score: Optional[float] = None
    actionable_insights: Optional[List[str]] = None
   
    class Config:
        extra = "allow" 


class AnalysisOut(BaseModel):
    """
    Modèle pour la sortie d'une analyse IA.
    Utilisé dans les réponses des requêtes GET /feedback/{id} et GET /insights.
    """
    feedback_id: int = Field(..., example=1)
    analysis: AnalysisDataOut 
    analysis_timestamp: datetime = Field(..., example=datetime.now())

    class Config:
        from_attributes = True


class RecommendationOut(BaseModel):
    """
    Modèle pour la sortie d'une recommandation extraite.
    Utilisé dans la réponse de la requête GET /recommendations.
    """
    feedback_id: int = Field(..., example=1)
    recommendation: str = Field(..., example="Former le personnel à l'accueil.")
    timestamp: datetime = Field(..., example=datetime.now())

    class Config:
        from_attributes = True