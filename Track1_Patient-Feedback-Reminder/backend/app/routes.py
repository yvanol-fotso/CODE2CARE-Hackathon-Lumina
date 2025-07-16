from fastapi import APIRouter, HTTPException, status, Depends
from app.models import FeedbackIn, AnalysisIn, FeedbackOut, AnalysisOut, RecommendationOut 
from app.database import get_connection 
import asyncpg 
import logging
from typing import List, Optional
import json 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# --- Route POST /feedback ---
@router.post("/feedback", status_code=status.HTTP_201_CREATED, response_model=FeedbackOut)
async def create_feedback(
    feedback: FeedbackIn,
    conn: asyncpg.Connection = Depends(get_connection) 
):
    try:
        async with conn.transaction():
            insert_query = """
                INSERT INTO feedbacks (patient_id, text, note, emoji)
                VALUES ($1, $2, $3, $4)
                RETURNING id, patient_id, text, note, emoji, timestamp;
            """

            inserted_row = await conn.fetchrow(
                insert_query,
                feedback.patient_id.strip(),
                feedback.text.strip(),
                feedback.note,
                feedback.emoji.strip() if feedback.emoji else None
            )

            if inserted_row is None:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail="Échec de l'insertion du feedback.")

            feedback_data = {
                "id": inserted_row["id"],
                "patient_id": inserted_row["patient_id"],
                "text": inserted_row["text"],
                "note": inserted_row["note"],
                "emoji": inserted_row["emoji"],
                "timestamp": inserted_row["timestamp"].isoformat()
            }

            return {
                "success": True,
                "message": "Feedback enregistré avec succès.",
                "feedback_id": inserted_row["id"],
                "data": feedback_data 
            }

    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error: {e.diag.message_primary}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e.diag.message_primary}"
        )
    except Exception as e:
        logger.exception("Erreur inattendue lors de l'enregistrement du feedback.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue lors du traitement du feedback: {e}"
        )

# --- Route GET /feedbacks ---
@router.get("/feedbacks", response_model=dict) 
async def get_all_feedbacks(
    conn: asyncpg.Connection = Depends(get_connection)
):
    try:
        rows = await conn.fetch("SELECT id, patient_id, text, note, emoji, timestamp FROM feedbacks ORDER BY timestamp DESC;")

        if not rows:
            return {
                "success": True,
                "message": "Aucun feedback enregistré pour le moment.",
                "data": []
            }

        feedbacks = []
        for row in rows:
            feedbacks.append({
                "id": row["id"], 
                "patient_id": row["patient_id"],
                "text": row["text"],
                "note": row["note"],
                "emoji": row["emoji"],
                "timestamp": row["timestamp"].isoformat()
            })

        return {
            "success": True,
            "message": f"{len(feedbacks)} feedback(s) trouvé(s).",
            "data": feedbacks
        }

    except Exception as e:
        logger.exception("Erreur lors de la récupération des feedbacks.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la récupération des feedbacks: {e}"
        )

# --- Route GET /feedback/{feedback_id} ---
@router.get("/feedback/{feedback_id}", response_model=dict) 
async def get_feedback_with_analysis(
    feedback_id: int,
    conn: asyncpg.Connection = Depends(get_connection)
):
    try:
        # take le feedback brut
        feedback_row = await conn.fetchrow("""
            SELECT id, patient_id, text, note, emoji, timestamp
            FROM feedbacks
            WHERE id = $1;
        """, feedback_id)

        if not feedback_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback introuvable.")

        feedback = {
            "id": feedback_row["id"],
            "patient_id": feedback_row["patient_id"],
            "text": feedback_row["text"],
            "note": feedback_row["note"],
            "emoji": feedback_row["emoji"],
            "timestamp": feedback_row["timestamp"].isoformat()
        }

        # find l'analyse associée
        analysis_row = await conn.fetchrow("""
            SELECT analysis, analysis_timestamp
            FROM ai_analysis
            WHERE feedback_id = $1;
        """, feedback_id)

        analysis = None
        if analysis_row:
            analysis = {
                "data": analysis_row["analysis"],
                "timestamp": analysis_row["analysis_timestamp"].isoformat()
            }

        return {
            "success": True,
            "feedback": feedback,
            "analysis": analysis
        }

    except HTTPException as http_err:
        raise http_err 

    except Exception as e:
        logger.exception(f"Erreur lors de la récupération du feedback ID {feedback_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la récupération du feedback: {e}"
        )

# --- Route POST /feedback/{feedback_id}/analyze ---
@router.post("/feedback/{feedback_id}/analyze", response_model=dict)
async def save_analysis_for_feedback(
    feedback_id: int,
    payload: AnalysisIn,
    conn: asyncpg.Connection = Depends(get_connection)
):
    try:
        async with conn.transaction():
            # Check que le feedback existe
            feedback_exists = await conn.fetchval("SELECT id FROM feedbacks WHERE id = $1;", feedback_id)
            if feedback_exists is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback introuvable.")

            # Check si une analyse existe déjà pour ce feedback_id
            analysis_exists = await conn.fetchval("SELECT id FROM ai_analysis WHERE feedback_id = $1;", feedback_id)
            if analysis_exists is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Une analyse existe déjà pour ce feedback.")
            await conn.execute("""
                INSERT INTO ai_analysis (feedback_id, analysis)
                VALUES ($1, $2::jsonb);
            """, feedback_id, payload.analysis) 

            return {
                "success": True,
                "message": "Analyse IA enregistrée avec succès."
            }

    except HTTPException as http_err:
        raise http_err

    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"PostgreSQL error: {e.diag.message_primary}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de la base de données: {e.diag.message_primary}"
        )
    except Exception as e:
        logger.exception(f"Erreur lors de l'enregistrement de l'analyse pour le feedback {feedback_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erreur serveur lors de l'enregistrement de l'analyse: {e}")

# --- Route GET /insights ---
@router.get("/insights", response_model=dict)
async def get_all_analyses(
    conn: asyncpg.Connection = Depends(get_connection)
):
    try:
        rows = await conn.fetch("""
            SELECT feedback_id, analysis, analysis_timestamp
            FROM ai_analysis
            ORDER BY analysis_timestamp DESC;
        """)

        if not rows:
            return {
                "success": True,
                "message": "Aucune analyse IA enregistrée pour le moment.",
                "data": []
            }

        insights = []
        for row in rows:
            insights.append({
                "feedback_id": row["feedback_id"],
                "analysis": row["analysis"], 
                "timestamp": row["analysis_timestamp"].isoformat()
            })

        return {
            "success": True,
            "message": f"{len(insights)} analyse(s) IA trouvée(s).",
            "data": insights
        }

    except Exception as e:
        logger.exception("Erreur lors de la récupération des analyses IA.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la récupération des insights: {e}"
        )

# --- Route GET /recommendations ---
@router.get("/recommendations", response_model=dict)
async def get_all_recommendations(
    conn: asyncpg.Connection = Depends(get_connection)
):
    try:
        rows = await conn.fetch("""
            SELECT feedback_id, analysis, analysis_timestamp
            FROM ai_analysis
            ORDER BY analysis_timestamp DESC;
        """)

        if not rows:
            return {
                "success": True,
                "message": "Aucune analyse disponible pour extraire des recommandations.",
                "data": []
            }

        recommendations = []
        for row in rows:
            feedback_id = row["feedback_id"]
            analysis = row["analysis"] 
            timestamp = row["analysis_timestamp"]

            if analysis and isinstance(analysis, dict):
                insights = analysis.get("actionable_insights", [])
                if isinstance(insights, list):
                    for rec in insights:
                        recommendations.append({
                            "feedback_id": feedback_id,
                            "recommendation": rec,
                            "timestamp": timestamp.isoformat()
                        })

        if not recommendations:
            return {
                "success": True,
                "message": "Aucune recommandation trouvée dans les analyses.",
                "data": []
            }

        return {
            "success": True,
            "message": f"{len(recommendations)} recommandation(s) extraite(s).",
            "data": recommendations
        }

    except Exception as e:
        logger.exception("Erreur lors de la récupération des recommandations.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de l'extraction des recommandations: {e}"
        )