from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Παίρνουμε το URL της βάσης από τις ρυθμίσεις του Docker (environment variables)
# Αν δεν το βρει, χρησιμοποιεί ένα default για ασφάλεια
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@db:5432/ev_charging_db")

# Δημιουργία του "Engine" (ο κινητήρας της σύνδεσης)
engine = create_engine(DATABASE_URL)

# Δημιουργία του Session (η τρέχουσα συνομιλία με τη βάση)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Η βάση για όλα τα Models μας
Base = declarative_base()

# Helper function για να παίρνουμε το DB session στα endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()