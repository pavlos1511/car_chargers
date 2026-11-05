from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# --- ΝΕΟ: Πίνακας Χρηστών (Απλοποιημένος) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String) # Plain text password (λόγω εργασίας)
    
    # Ρόλος χρήστη (π.χ. 'admin' ή 'driver') - Θα φανεί χρήσιμο μετά
    role = Column(String, default="driver") 

# --- Τα υπόλοιπα models παραμένουν ίδια ---
class ChargePoint(Base):
    __tablename__ = "charge_points"
    point_id = Column(String, primary_key=True, index=True) 
    provider_name = Column(String, default="bestPowerGR") 
    lon = Column(String)
    lat = Column(String)
    status = Column(String, default="offline")
    cap = Column(Integer)
    kwh_price = Column(Float, nullable=True)
    reservation_end_time = Column(DateTime, nullable=True)
    sessions = relationship("ChargingSession", back_populates="point")
    events = relationship("PointEvent", back_populates="point")

class ChargingSession(Base):
    __tablename__ = "charging_sessions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    point_id = Column(String, ForeignKey("charge_points.point_id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    start_soc = Column(Integer)
    end_soc = Column(Integer)
    total_kwh = Column(Float)
    cost_per_kwh = Column(Float)
    total_amount = Column(Float)
    point = relationship("ChargePoint", back_populates="sessions")

class PointEvent(Base):
    __tablename__ = "point_events"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    point_id = Column(String, ForeignKey("charge_points.point_id"))
    event_timestamp = Column(DateTime, default=datetime.utcnow)
    old_state = Column(String)
    new_state = Column(String)
    point = relationship("ChargePoint", back_populates="events")