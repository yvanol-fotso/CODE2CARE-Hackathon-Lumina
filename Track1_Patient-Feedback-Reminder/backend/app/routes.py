from fastapi import APIRouter, HTTPException, status, Depends
import app.models
from app.database import get_connection
import asyncpg
import logging
from typing import List, Optional, Dict, Any
import json
import httpx
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

AI_API_URL = os.getenv("AI_API_URL")
if not AI_API_URL:
    logger.error("AI_API_URL environment variable not set. AI analysis will not function.")

async def call_ai_analysis_service(
    feedback_text: str,
    patient_id: Optional[str] = None,
    patient_age: Optional[float] = None,
    patient_gender: Optional[str] = None,
    department: Optional[str] = None,
    wait_time_min: Optional[float] = None,
    resolution_time_min: Optional[float] = None,
    rating: Optional[float] = None
) -> Dict[str, Any]:
    """
    Appelle le service AI externe pour obtenir l'analyse de sentiment, les recommandations,
    et d'autres analyses détaillées pour un texte de feedback donné,
    en envoyant un payload plat comme spécifié.
    Parse la réponse pour l'adapter à la structure de notre modèle interne AnalysisIn.
    """
    if not AI_API_URL:
        logger.error("AI_API_URL is not set, cannot call external AI service.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Service AI externe non configuré.")

    try:
        async with httpx.AsyncClient() as client:
            ai_request_body = {
                "feedback_text": feedback_text,
                "patient_id": patient_id,
                "patient_age": patient_age,
                "patient_gender": patient_gender,
                "department": department,
                "wait_time_min": wait_time_min,
                "resolution_time_min": resolution_time_min,
                "rating": rating
            }
            ai_request_body = {k: v for k, v in ai_request_body.items() if v is not None}

            response = await client.post(AI_API_URL, json=ai_request_body, timeout=30.0)
            response.raise_for_status()
            raw_ai_result = response.json()

            validated_overall_response = app.models.ExternalAIOverallResponse(**raw_ai_result)
            ai_response_content = validated_overall_response.data 

            analysis_data_for_db = app.models.AnalysisDataIn(
                primary_sentiment=ai_response_content.ai_analysis.primary_sentiment,
                confidence_score=ai_response_content.ai_analysis.confidence_score,
                actionable_insights=ai_response_content.ai_analysis.actionable_insights,
                keywords=ai_response_content.ai_analysis.key_themes,
                personalized_message_draft=ai_response_content.ai_analysis.personalized_message_draft,
                contextual_factors=ai_response_content.ai_analysis.contextual_factors,
                department_specific_insights=ai_response_content.ai_analysis.department_specific_insights,
                emotional_intensity=ai_response_content.ai_analysis.emotional_intensity,
                key_themes=ai_response_content.ai_analysis.key_themes,
                patient_behavior_analysis=ai_response_content.ai_analysis.patient_behavior_analysis,
                sentiment_explanation=ai_response_content.ai_analysis.sentiment_explanation,
                urgency_level=ai_response_content.ai_analysis.urgency_level,
                contextual_data=ai_response_content.contextual_data,
                risk_factors=ai_response_content.risk_factors,
                sticker_analysis=ai_response_content.sticker_analysis
            )

            recommendations_for_db = ai_response_content.recommendations

            return {
                "analysis": analysis_data_for_db.model_dump(mode='json'),
                "recommendations": recommendations_for_db
            }

    except httpx.RequestError as e:
        logger.error(f"Erreur de connexion au service AI externe: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Impossible de se connecter au service AI externe: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur du service AI externe (statut {e.response.status_code}): {e.response.text}")
        logger.error(f"Réponse complète de l'erreur du service AI: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code,
                            detail=f"Erreur du service AI externe: {e.response.text[:200]}...")
    except json.JSONDecodeError:
        logger.error("Réponse invalide (non-JSON) du service AI externe.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Réponse invalide du service AI externe.")
    except Exception as e:
        logger.exception("Erreur inattendue lors de l'appel au service AI externe ou de l'analyse de sa réponse.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur inattendue lors de l'intégration AI: {e}")


# --- Route POST /feedback ---
@router.post("/feedback", status_code=status.HTTP_201_CREATED, response_model=app.models.FeedbackOut)
async def create_feedback(
    feedback: app.models.FeedbackIn,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Enregistre un nouveau feedback patient dans la base de données.
    """
    try:
        async with conn.transaction():
            insert_query = """
                INSERT INTO feedbacks (patient_id, text, note, emoji, patient_age, patient_gender, department, wait_time_min, resolution_time_min)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, patient_id, text, note, emoji, timestamp;
            """

            inserted_row = await conn.fetchrow(
                insert_query,
                feedback.patient_id.strip(),
                feedback.text.strip(),
                feedback.note,
                feedback.emoji.strip() if feedback.emoji else None,
                feedback.patient_age,
                feedback.patient_gender.strip() if feedback.patient_gender else None,
                feedback.department.strip() if feedback.department else None,
                feedback.wait_time_min,
                feedback.resolution_time_min
            )

            if inserted_row is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Échec de l'insertion du feedback.")

            return app.models.FeedbackOut(
                id=inserted_row["id"],
                patient_id=inserted_row["patient_id"],
                text=inserted_row["text"],
                note=inserted_row["note"],
                emoji=inserted_row["emoji"],
                timestamp=inserted_row["timestamp"]
            )

    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error during feedback creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e}"
        )
    except Exception as e:
        logger.exception("Erreur inattendue lors de l'enregistrement du feedback.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue lors du traitement du feedback: {e}"
        )

# --- NOUVELLE ROUTE: POST /feedback_and_analyze ---
@router.post("/feedback_and_analyze", status_code=status.HTTP_201_CREATED, response_model=app.models.FeedbackAndAnalysisResponse)
async def create_feedback_and_analyze(
    feedback: app.models.FeedbackIn,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Enregistre un nouveau feedback patient et déclenche immédiatement son analyse IA,
    retournant le feedback créé et l'analyse IA.
    """
    try:
        async with conn.transaction():
            # Sauvegarder le feedback
            insert_feedback_query = """
                INSERT INTO feedbacks (patient_id, text, note, emoji, patient_age, patient_gender, department, wait_time_min, resolution_time_min)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id, patient_id, text, note, emoji, timestamp;
            """
            inserted_feedback_row = await conn.fetchrow(
                insert_feedback_query,
                feedback.patient_id.strip(),
                feedback.text.strip(),
                feedback.note,
                feedback.emoji.strip() if feedback.emoji else None,
                feedback.patient_age,
                feedback.patient_gender.strip() if feedback.patient_gender else None,
                feedback.department.strip() if feedback.department else None,
                feedback.wait_time_min,
                feedback.resolution_time_min
            )

            if inserted_feedback_row is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Échec de l'insertion du feedback.")

            created_feedback = app.models.FeedbackOut(
                id=inserted_feedback_row["id"],
                patient_id=inserted_feedback_row["patient_id"],
                text=inserted_feedback_row["text"],
                note=inserted_feedback_row["note"],
                emoji=inserted_feedback_row["emoji"],
                timestamp=inserted_feedback_row["timestamp"]
            )

            # Préparer les données pour l'appel au service AI
            ai_input_data = {
                "feedback_text": feedback.text.strip(),
                "patient_id": feedback.patient_id.strip(),
                "patient_age": feedback.patient_age,
                "patient_gender": feedback.patient_gender,
                "department": feedback.department,
                "wait_time_min": feedback.wait_time_min,
                "resolution_time_min": feedback.resolution_time_min,
                "rating": float(feedback.note) if feedback.note is not None else None
            }

            # Appele le service AI externe
            ai_response_data_parsed = await call_ai_analysis_service(**ai_input_data)

            # Convertir en modèle Pydantic AnalysisIn pour validation avant sauvegarde
            analysis_payload = app.models.AnalysisIn(**ai_response_data_parsed)

            # add l'analyse et les recommandations dans la table ai_analysis
            insert_analysis_query = """
                INSERT INTO ai_analysis (feedback_id, analysis, recommendations)
                VALUES ($1, $2::jsonb, $3::jsonb)
                RETURNING id, feedback_id, analysis, recommendations, analysis_timestamp;
            """
            inserted_analysis_row = await conn.fetchrow(
                insert_analysis_query,
                created_feedback.id,
                json.dumps(analysis_payload.analysis.model_dump(mode='json')),
                json.dumps(analysis_payload.recommendations) if analysis_payload.recommendations is not None else '[]'
            )

            if inserted_analysis_row is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Échec de l'enregistrement de l'analyse IA.")

            # Préparer les données d'analyse pour le modèle de sortie
            analysis_data_raw = inserted_analysis_row["analysis"]
            if isinstance(analysis_data_raw, str):
                analysis_dict = json.loads(analysis_data_raw)
            else: # Assume it's already a dict or None
                analysis_dict = analysis_data_raw or {}

            # Préparer les données de recommandations pour le modèle de sortie
            recommendations_data_raw = inserted_analysis_row["recommendations"]
            if isinstance(recommendations_data_raw, str):
                recommendations_list = json.loads(recommendations_data_raw)
            else: # Assume it's already a list or None
                recommendations_list = recommendations_data_raw or []

            created_analysis = app.models.AnalysisOut(
                feedback_id=inserted_analysis_row["feedback_id"],
                analysis=app.models.AnalysisDataOut(**analysis_dict),
                recommendations=recommendations_list,
                analysis_timestamp=inserted_analysis_row["analysis_timestamp"]
            )

            # Retourner la réponse combinée
            return app.models.FeedbackAndAnalysisResponse(
                feedback=created_feedback,
                analysis=created_analysis
            )

    except HTTPException as http_err:
        raise http_err
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error during combined feedback and analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e}"
        )
    except Exception as e:
        logger.exception("Erreur inattendue lors de la création et de l'analyse du feedback.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue lors du traitement: {e}"
        )


# --- Route GET /feedbacks ---
@router.get("/feedbacks", response_model=List[app.models.FeedbackOut])
async def get_all_feedbacks(
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère tous les feedbacks patients enregistrés.
    """
    try:
        rows = await conn.fetch("SELECT id, patient_id, text, note, emoji, timestamp FROM feedbacks ORDER BY timestamp DESC;")

        if not rows:
            return []

        feedbacks = [
            app.models.FeedbackOut(
                id=row["id"],
                patient_id=row["patient_id"],
                text=row["text"],
                note=row["note"],
                emoji=row["emoji"],
                timestamp=row["timestamp"]
            )
            for row in rows
        ]
        return feedbacks

    except Exception as e:
        logger.exception("Erreur lors de la récupération des feedbacks.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la récupération des feedbacks: {e}"
        )

# --- Route GET /feedback/{feedback_id} ---
@router.get("/feedback/{feedback_id}", response_model=Dict[str, Any])
async def get_feedback_with_analysis(
    feedback_id: int,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère un feedback spécifique et son analyse IA associée, si elle existe.
    """
    try:
        feedback_row = await conn.fetchrow("""
            SELECT id, patient_id, text, note, emoji, timestamp, patient_age, patient_gender, department, wait_time_min, resolution_time_min
            FROM feedbacks
            WHERE id = $1;
        """, feedback_id)

        if not feedback_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback introuvable.")

        feedback = app.models.FeedbackOut(
            id=feedback_row["id"],
            patient_id=feedback_row["patient_id"],
            text=feedback_row["text"],
            note=feedback_row["note"],
            emoji=feedback_row["emoji"],
            timestamp=feedback_row["timestamp"]
        )

        analysis_row = await conn.fetchrow("""
            SELECT analysis, recommendations, analysis_timestamp
            FROM ai_analysis
            WHERE feedback_id = $1;
        """, feedback_id)

        analysis_out = None
        if analysis_row:
            # Désérialiser explicitement la chaîne JSON en dict
            analysis_data_raw = analysis_row["analysis"]
            if isinstance(analysis_data_raw, str):
                analysis_dict = json.loads(analysis_data_raw)
            else:
                analysis_dict = analysis_data_raw or {}

            # Désérialiser explicitement la chaîne JSON en liste
            recommendations_data_raw = analysis_row["recommendations"]
            if isinstance(recommendations_data_raw, str):
                recommendations_list = json.loads(recommendations_data_raw)
            else:
                recommendations_list = recommendations_data_raw or []

            analysis_out = app.models.AnalysisOut(
                feedback_id=feedback_id,
                analysis=app.models.AnalysisDataOut(**analysis_dict),
                recommendations=recommendations_list,
                analysis_timestamp=analysis_row["analysis_timestamp"]
            )

        return {
            "success": True,
            "feedback": feedback.model_dump(),
            "analysis": analysis_out.model_dump() if analysis_out else None
        }

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération du feedback ID {feedback_id} avec analyse.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la récupération du feedback: {e}"
        )

# --- Route POST /feedback/{feedback_id}/analyze ---
@router.post("/feedback/{feedback_id}/analyze", status_code=status.HTTP_201_CREATED, response_model=app.models.AnalysisOut)
async def analyze_and_save_feedback(
    feedback_id: int,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Analyse le texte d'un feedback existant via l'API IA externe
    et enregistre l'analyse et les recommandations dans la base de données.
    Ceci est l'endpoint original pour analyser un feedback déjà existant.
    """
    try:
        async with conn.transaction():
            # 1. Vérifier si le feedback existe et récupérer son texte et autres données
            feedback_row = await conn.fetchrow("""
                SELECT text, patient_id, note, patient_age, patient_gender, department, wait_time_min, resolution_time_min
                FROM feedbacks WHERE id = $1;
            """, feedback_id)
            if feedback_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback introuvable.")
            
            feedback_text = feedback_row["text"]
            patient_id_from_db = feedback_row["patient_id"]
            note_from_db = feedback_row["note"]
            patient_age_from_db = feedback_row.get("patient_age")
            patient_gender_from_db = feedback_row.get("patient_gender")
            department_from_db = feedback_row.get("department")
            wait_time_min_from_db = feedback_row.get("wait_time_min")
            resolution_time_min_from_db = feedback_row.get("resolution_time_min")

            # 2. Vérifier si une analyse existe déjà pour ce feedback_id
            analysis_exists = await conn.fetchval("SELECT id FROM ai_analysis WHERE feedback_id = $1;", feedback_id)
            if analysis_exists is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Une analyse existe déjà pour ce feedback.")

            # 3. Appeler le service AI externe avec les données contextuelles disponibles
            ai_response_data_parsed = await call_ai_analysis_service(
                feedback_text=feedback_text,
                patient_id=patient_id_from_db,
                patient_age=patient_age_from_db,
                patient_gender=patient_gender_from_db,
                department=department_from_db,
                wait_time_min=wait_time_min_from_db,
                resolution_time_min=resolution_time_min_from_db,
                rating=float(note_from_db) if note_from_db is not None else None
            )

            # Convertir en modèle Pydantic AnalysisIn pour validation avant sauvegarde
            analysis_payload = app.models.AnalysisIn(**ai_response_data_parsed)

            # 4. Insérer l'analyse et les recommandations dans la table ai_analysis
            insert_query = """
                INSERT INTO ai_analysis (feedback_id, analysis, recommendations)
                VALUES ($1, $2::jsonb, $3::jsonb)
                RETURNING id, feedback_id, analysis, recommendations, analysis_timestamp;
            """
            inserted_row = await conn.fetchrow(
                insert_query,
                feedback_id,
                json.dumps(analysis_payload.analysis.model_dump(mode='json')),
                json.dumps(analysis_payload.recommendations) if analysis_payload.recommendations is not None else '[]'
            )

            if inserted_row is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Échec de l'enregistrement de l'analyse IA.")

            # Préparer les données d'analyse pour le modèle de sortie
            analysis_data_raw = inserted_row["analysis"]
            if isinstance(analysis_data_raw, str):
                analysis_dict = json.loads(analysis_data_raw)
            else:
                analysis_dict = analysis_data_raw or {}

            # Préparer les données de recommandations pour le modèle de sortie
            recommendations_data_raw = inserted_row["recommendations"]
            if isinstance(recommendations_data_raw, str):
                recommendations_list = json.loads(recommendations_data_raw)
            else:
                recommendations_list = recommendations_data_raw or []

            return app.models.AnalysisOut(
                feedback_id=inserted_row["feedback_id"],
                analysis=app.models.AnalysisDataOut(**analysis_dict),
                recommendations=recommendations_list,
                analysis_timestamp=inserted_row["analysis_timestamp"]
            )

    except HTTPException as http_err:
        raise http_err
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error during analysis saving: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e}"
        )
    except Exception as e:
        logger.exception(f"Erreur inattendue lors de l'enregistrement de l'analyse pour le feedback {feedback_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur serveur lors de l'enregistrement de l'analyse: {e}")

# --- Route GET /insights ---
@router.get("/insights", response_model=List[app.models.AnalysisOut])
async def get_all_analyses(
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère toutes les analyses IA enregistrées.
    """
    try:
        rows = await conn.fetch("""
            SELECT feedback_id, analysis, recommendations, analysis_timestamp
            FROM ai_analysis
            ORDER BY analysis_timestamp DESC;
        """)

        if not rows:
            return []

        insights = []
        for row in rows:
            # Désérialiser explicitement la chaîne JSON en dict
            analysis_data_raw = row["analysis"]
            if isinstance(analysis_data_raw, str):
                analysis_dict = json.loads(analysis_data_raw)
            else:
                analysis_dict = analysis_data_raw or {}

            # Désérialiser explicitement la chaîne JSON en liste
            recommendations_data_raw = row["recommendations"]
            if isinstance(recommendations_data_raw, str):
                recommendations_list = json.loads(recommendations_data_raw)
            else:
                recommendations_list = recommendations_data_raw or []

            insights.append(
                app.models.AnalysisOut(
                    feedback_id=row["feedback_id"],
                    analysis=app.models.AnalysisDataOut(**analysis_dict),
                    recommendations=recommendations_list,
                    analysis_timestamp=row["analysis_timestamp"]
                )
            )
        return insights

    except Exception as e:
        logger.exception("Erreur lors de la récupération des analyses IA.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la récupération des insights: {e}"
        )

# --- Route GET /recommendations ---
@router.get("/recommendations", response_model=List[app.models.RecommendationOut])
async def get_all_recommendations(
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère toutes les recommandations extraites des analyses IA.
    """
    try:
        rows = await conn.fetch("""
            SELECT feedback_id, recommendations, analysis_timestamp
            FROM ai_analysis
            WHERE recommendations IS NOT NULL AND jsonb_array_length(recommendations) > 0
            ORDER BY analysis_timestamp DESC;
        """)

        if not rows:
            return []

        recommendations_list = []
        for row in rows:
            feedback_id = row["feedback_id"]
            # Désérialiser explicitement la chaîne JSON en list
            recommendations_jsonb_raw = row["recommendations"]
            if isinstance(recommendations_jsonb_raw, str):
                recommendations_jsonb = json.loads(recommendations_jsonb_raw)
            else:
                recommendations_jsonb = recommendations_jsonb_raw or []
            
            timestamp = row["analysis_timestamp"]

            if recommendations_jsonb and isinstance(recommendations_jsonb, list):
                for rec_text in recommendations_jsonb:
                    recommendations_list.append(
                        app.models.RecommendationOut(
                            feedback_id=feedback_id,
                            recommendation=rec_text,
                            timestamp=timestamp
                        )
                    )
        return recommendations_list

    except Exception as e:
        logger.exception("Erreur lors de la récupération des recommandations.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de l'extraction des recommandations: {e}"
        )

# --- NOUVELLES ROUTES: Demandes de Rappel ---

@router.post("/recall-requests", status_code=status.HTTP_201_CREATED, response_model=app.models.RecallRequestOut)
async def create_recall_request(
    recall_request: app.models.RecallRequestIn,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Crée une nouvelle demande de rappel/rendez-vous par un patient.
    """
    try:
        insert_query = """
            INSERT INTO recall_requests (patient_id, request_object, requested_date)
            VALUES ($1, $2, $3)
            RETURNING id, patient_id, request_object, requested_date, request_timestamp, status, approved_by, approval_date;
        """
        inserted_row = await conn.fetchrow(
            insert_query,
            recall_request.patient_id.strip(),
            recall_request.request_object.strip(),
            recall_request.requested_date
        )

        if inserted_row is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Échec de la création de la demande de rappel.")

        return app.models.RecallRequestOut(
            id=inserted_row["id"],
            patient_id=inserted_row["patient_id"],
            request_object=inserted_row["request_object"],
            requested_date=inserted_row["requested_date"],
            request_timestamp=inserted_row["request_timestamp"],
            status=inserted_row["status"],
            approved_by=inserted_row["approved_by"],
            approval_date=inserted_row["approval_date"]
        )
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error during recall request creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e}"
        )
    except Exception as e:
        logger.exception("Erreur inattendue lors de la création de la demande de rappel.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la création de la demande de rappel: {e}"
        )

@router.get("/recall-requests", response_model=List[app.models.RecallRequestOut])
async def get_all_recall_requests(
    status_filter: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère toutes les demandes de rappel/rendez-vous, avec option de filtrage par statut.
    """
    try:
        query = """
            SELECT id, patient_id, request_object, requested_date, request_timestamp, status, approved_by, approval_date
            FROM recall_requests
        """
        params = []
        if status_filter:
            query += " WHERE status = $1"
            params.append(status_filter.strip())
        query += " ORDER BY request_timestamp DESC;"

        rows = await conn.fetch(query, *params)

        return [app.models.RecallRequestOut(**row) for row in rows]
    except Exception as e:
        logger.exception("Erreur lors de la récupération des demandes de rappel.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la récupération des demandes de rappel: {e}"
        )

@router.get("/recall-requests/{request_id}", response_model=app.models.RecallRequestOut)
async def get_recall_request_by_id(
    request_id: int, # Bon parameter name
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère une demande de rappel/rendez-vous spécifique par son ID.
    """
    try:
        row = await conn.fetchrow("""
            SELECT id, patient_id, request_object, requested_date, request_timestamp, status, approved_by, approval_date
            FROM recall_requests
            WHERE id = $1;
        """, request_id) # On passe request_id icci

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande de rappel introuvable.")

        return app.models.RecallRequestOut(**row)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération de la demande de rappel ID {request_id}.") # Use request_id here
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la récupération de la demande de rappel: {e}"
        )

@router.put("/recall-requests/{request_id}/status", response_model=app.models.RecallRequestOut)
async def update_recall_request_status(
    request_id: int,
    new_status: str,
    approved_by: str,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Met à jour le statut d'une demande de rappel/rendez-vous.
    """
    if new_status not in ["pending", "approved", "rejected", "completed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Statut invalide.")

    try:
        async with conn.transaction():
            update_query = """
                UPDATE recall_requests
                SET status = $1, approved_by = $2, approval_date = CURRENT_TIMESTAMP
                WHERE id = $3
                RETURNING id, patient_id, request_object, requested_date, request_timestamp, status, approved_by, approval_date;
            """
            updated_row = await conn.fetchrow(
                update_query,
                new_status.strip(),
                approved_by.strip(),
                request_id
            )

            if updated_row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande de rappel introuvable ou non mise à jour.")

            return app.models.RecallRequestOut(**updated_row)
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error during recall request status update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e}"
        )
    except Exception as e:
        logger.exception(f"Erreur inattendue lors de la mise à jour du statut de la demande de rappel ID {request_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la mise à jour du statut: {e}"
        )

# ---  ROUTES: Messages Personnalisés ---

@router.post("/personalized-messages", status_code=status.HTTP_201_CREATED, response_model=app.models.PersonalizedMessageOut)
async def create_personalized_message(
    message: app.models.PersonalizedMessageIn,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Enregistre un nouveau message personnalisé envoyé à un patient.
    """
    try:
        insert_query = """
            INSERT INTO personalized_messages (recall_request_id, patient_id, message_content, sent_by, ai_message_analysis)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id, recall_request_id, patient_id, message_content, sent_by, sent_timestamp, ai_message_analysis;
        """
        inserted_row = await conn.fetchrow(
            insert_query,
            message.recall_request_id,
            message.patient_id.strip(),
            message.message_content.strip(),
            message.sent_by.strip(),
            message.ai_message_analysis
        )

        if inserted_row is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Échec de l'enregistrement du message personnalisé.")

        return app.models.PersonalizedMessageOut(
            id=inserted_row["id"],
            recall_request_id=inserted_row["recall_request_id"],
            patient_id=inserted_row["patient_id"],
            message_content=inserted_row["message_content"],
            sent_by=inserted_row["sent_by"],
            sent_timestamp=inserted_row["sent_timestamp"],
            ai_message_analysis=inserted_row["ai_message_analysis"]
        )
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error during personalized message creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e}"
        )
    except Exception as e:
        logger.exception("Erreur inattendue lors de l'enregistrement du message personnalisé.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de l'enregistrement du message personnalisé: {e}"
        )

@router.get("/personalized-messages", response_model=List[app.models.PersonalizedMessageOut])
async def get_all_personalized_messages(
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère toutes les messages personnalisés envoyés.
    """
    try:
        rows = await conn.fetch("""
            SELECT id, recall_request_id, patient_id, message_content, sent_by, sent_timestamp, ai_message_analysis
            FROM personalized_messages
            ORDER BY sent_timestamp DESC;
        """)

        return [app.models.PersonalizedMessageOut(**row) for row in rows]
    except Exception as e:
        logger.exception("Erreur lors de la récupération des messages personnalisés.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la récupération des messages personnalisés: {e}"
        )

@router.get("/personalized-messages/{message_id}", response_model=app.models.PersonalizedMessageOut)
async def get_personalized_message_by_id(
    message_id: int,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère un message personnalisé spécifique par son ID.
    """
    try:
        row = await conn.fetchrow("""
            SELECT id, recall_request_id, patient_id, message_content, sent_by, sent_timestamp, ai_message_analysis
            FROM personalized_messages
            WHERE id = $1;
        """, message_id)

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message personnalisé introuvable.")

        return app.models.PersonalizedMessageOut(**row)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération du message personnalisé ID {message_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la récupération du message personnalisé: {e}"
        )

@router.get("/personalized-messages/patient/{patient_id}", response_model=List[app.models.PersonalizedMessageOut])
async def get_personalized_messages_for_patient(
    patient_id: str,
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Récupère tous les messages personnalisés envoyés à un patient spécifique.
    """
    try:
        rows = await conn.fetch("""
            SELECT id, recall_request_id, patient_id, message_content, sent_by, sent_timestamp, ai_message_analysis
            FROM personalized_messages
            WHERE patient_id = $1
            ORDER BY sent_timestamp DESC;
        """, patient_id.strip())

        return [app.models.PersonalizedMessageOut(**row) for row in rows]
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des messages personnalisés pour le patient {patient_id}.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Erreur serveur lors de la récupération des messages pour le patient: {e}"
        )
