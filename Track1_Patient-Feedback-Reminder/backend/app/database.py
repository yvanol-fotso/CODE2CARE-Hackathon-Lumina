# from pymongo import MongoClient
# from dotenv import load_dotenv
# import os

# load_dotenv()

# MONGO_URI = os.getenv("MONGO_URI")
# DB_NAME = os.getenv("DB_NAME")

# client = MongoClient(MONGO_URI)
# db = client[DB_NAME]
# feedbacks_collection = db["feedbacks"]




# ############################## PostgreSQL #############################

import asyncpg
from dotenv import load_dotenv
import os
import json 

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME_POSTGRES")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

_db_pool = None 

async def get_database_connection_pool():
    """
    Crée et retourne un pool de connexions asynchrones à PostgreSQL.
    Initialise également les tables si elles n'existent pas.
    """
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = await asyncpg.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                min_size=5, 
                max_size=10 
            )
            print("Pool de connexions PostgreSQL créé avec succès.")

            async with _db_pool.acquire() as conn:
                async with conn.transaction():
                    # Table des feedbacks bruts
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS feedbacks (
                            id SERIAL PRIMARY KEY,
                            patient_id TEXT NOT NULL,
                            text TEXT NOT NULL,
                            note INTEGER,
                            emoji TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            patient_age REAL, 
                            patient_gender TEXT,
                            department TEXT,
                            wait_time_min REAL,
                            resolution_time_min REAL
                        );
                    """)
                    print("Table 'feedbacks' vérifiée/créée.")

                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS ai_analysis (
                            id SERIAL PRIMARY KEY,
                            feedback_id INTEGER REFERENCES feedbacks(id) ON DELETE CASCADE,
                            analysis JSONB,
                            recommendations JSONB,
                            analysis_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    print("Table 'ai_analysis' vérifiée/créée analysis et recommendations JSONB.")

                    # Table des demandes de rappel/rendez-vous
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS recall_requests (
                            id SERIAL PRIMARY KEY,
                            patient_id TEXT NOT NULL,
                            request_object TEXT NOT NULL, 
                            requested_date DATE, 
                            request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status TEXT DEFAULT 'pending', -- Status of the request: 'pending', 'approved', 'rejected', 'completed'
                            approved_by TEXT,
                            approval_date TIMESTAMP 
                        );
                    """)
                    print("Table 'recall_requests' vérifiée/créée.")

                    # Table des messages personnalisés API 
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS personalized_messages (
                            id SERIAL PRIMARY KEY,
                            recall_request_id INTEGER REFERENCES recall_requests(id) ON DELETE CASCADE,
                            patient_id TEXT NOT NULL,
                            message_content TEXT NOT NULL,
                            sent_by TEXT NOT NULL, 
                            sent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            ai_message_analysis JSONB 
                        );
                    """)
                    print("Table 'personalized_messages' vérifiée/créée.")

            print("Base de données prête : toutes les tables configurées.")

        except Exception as e:
            print(f"Erreur lors de la création du pool ou de l'initialisation des tables : {e}")
            _db_pool = None 
            raise 

    return _db_pool

async def close_database_connection_pool(pool):
    """
    Ferme le pool de connexions asynchrones.
    """
    if pool:
        print("Fermeture du pool de connexions PostgreSQL...")
        await pool.close()
        print("Pool de connexions PostgreSQL fermé.")

async def get_connection():
    """
    Dépendance FastAPI pour obtenir une connexion du pool et la libérer automatiquement.
    """
    global _db_pool
    if _db_pool is None:
        _db_pool = await get_database_connection_pool()
        if _db_pool is None:
            raise RuntimeError("Le pool de base de données n'a pas pu être initialisé.")

    conn = await _db_pool.acquire()
    try:
        yield conn 
    finally:
        await _db_pool.release(conn)
