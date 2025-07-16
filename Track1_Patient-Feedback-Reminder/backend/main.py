from fastapi import FastAPI
from app.routes import router as feedback_router
from app.database import get_database_connection_pool, close_database_connection_pool

app = FastAPI(
    title="Patient Feedback API - Track 1",
    description="Backend API pour la gestion des feedbacks patients et leur analyse IA.",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    """
    connections à la base de données PostgreSQL au démarrage de l'application.
    """
    print("Démarrage de l'application : Connexion à la base de données...")
    app.state.db_pool = await get_database_connection_pool()
    print("Connexion à la base de données établie.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Ferme la connexion à la base de données PostgreSQL à l'arrêt de l'application.
    """
    print("Arrêt de l'application : Fermeture de la connexion à la base de données...")
    if hasattr(app.state, 'db_pool') and app.state.db_pool:
        await close_database_connection_pool(app.state.db_pool)
    print("Connexion à la base de données fermée.")


# --- Routes ---
app.include_router(feedback_router)

@app.get("/")
async def read_root():
    return {"message": "Bienvenue sur l'API Patient Feedback System !"}