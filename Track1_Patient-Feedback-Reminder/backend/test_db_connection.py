#################### MongoDB #####################
# from pymongo import MongoClient

# MONGO_URI = "mongodb://localhost:27017/" #Url part defaut
# DATABASE_NAME = "patient_feedback_db"

# try:
#     client = MongoClient(MONGO_URI)
#     db = client[DATABASE_NAME]

#     print(f"Connexion réussie à MongoDB. Base de données : {DATABASE_NAME}")
#     print("Collections existantes :", db.list_collection_names())

# except Exception as e:
#     print(f"Erreur de connexion à MongoDB : {e}")

# finally:
#     if 'client' in locals() and client:
#         client.close()
#         print("Connexion MongoDB fermée.")



################## PostgresSql ######################

# test_postgres_connection.py

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")    
DB_NAME = os.getenv("DB_NAME_POSTGRES")     
DB_USER = os.getenv("DB_USER")             
DB_PASSWORD = os.getenv("DB_PASSWORD")      

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id SERIAL PRIMARY KEY,
            text TEXT,
            note INTEGER,
            emoji TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit() 

    print("Connexion à PostgreSQL établie avec succès et table 'feedbacks' vérifiée/créée.")

except Exception as e:
    print(f"Erreur de connexion à PostgreSQL : {e}")
    raise

finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
        print("Connexion PostgreSQL fermée.")
 