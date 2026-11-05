from sqlalchemy.orm import Session
from sqlalchemy import func
import models, schemas
from datetime import datetime

# --- GET /points (με φίλτρο status) [cite: 60-61] ---
def get_points(db: Session, status: str = None):
    query = db.query(models.ChargePoint)
    if status:
        query = query.filter(models.ChargePoint.status == status)
    return query.all()

# --- GET /point/{id} [cite: 94] ---
def get_point_by_id(db: Session, point_id: str):
    point = db.query(models.ChargePoint).filter(models.ChargePoint.point_id == point_id).first()
    return point


# --- Admin Stats (για το Healthcheck) [cite: 39-41] ---
def get_stats(db: Session):
    total = db.query(models.ChargePoint).count()
    # Ως "online" θεωρούμε τα available, charging, reserved (όχι offline/malfunction)
    # Βλ. PDF σελ 3[cite: 57]: "Οι 4 πρώτες υποδηλώνουν ενεργή επικοινωνία"
    offline_count = db.query(models.ChargePoint).filter(
        models.ChargePoint.status.in_(['offline', 'malfunction'])
    ).count()
    
    return {
        "total": total,
        "offline": offline_count,
        "online": total - offline_count
    }
# --- Νέες προσθήκες για το Admin / Reset ---

def delete_all_points(db: Session):
    # Διαγράφουμε πρώτα τα sessions/events λόγω foreign keys
    db.query(models.ChargingSession).delete()
    db.query(models.PointEvent).delete()
    # Και μετά τα σημεία
    db.query(models.ChargePoint).delete()
    db.commit()

def create_point(db: Session, point_data: dict):
    # 1. Εξάγουμε το ID για να ψάξουμε
    p_id = str(point_data.get("pointid", point_data.get("id")))

    # 2. Έλεγχος: Υπάρχει ήδη στη βάση;
    existing_point = db.query(models.ChargePoint).filter(models.ChargePoint.point_id == p_id).first()

    if existing_point:
        # --- UPDATE SCENARIO ---
        # Αν υπάρχει, ενημερώνουμε τα πεδία του.
        # Χρησιμοποιούμε το .get(key, existing_value) για να μην χαλάσουμε δεδομένα αν το CSV έχει κενά.
        
        if "lon" in point_data:
            existing_point.lon = str(point_data["lon"])
        if "lat" in point_data:
            existing_point.lat = str(point_data["lat"])
        if "cap" in point_data:
            existing_point.cap = int(point_data["cap"])
        
        # Ειδική διαχείριση για την τιμή (costPerKwh ή kwhprice)
        new_price = point_data.get("costPerKwh", point_data.get("kwhprice"))
        if new_price is not None:
            existing_point.kwh_price = float(new_price)
            
        # Σημείωση: Συνήθως ΔΕΝ πειράζουμε το status στο Update, 
        # γιατί το σημείο μπορεί να φορτίζει εκείνη την ώρα!
        
        db.commit()
        db.refresh(existing_point)
        return existing_point

    else:
        # --- CREATE SCENARIO (Ο παλιός κώδικας) ---
        new_point = models.ChargePoint(
            point_id=p_id,
            provider_name=point_data.get("providerName", "unknown"),
            lon=str(point_data.get("lon")),
            lat=str(point_data.get("lat")),
            status="available", # Default μόνο για νέα σημεία
            cap=int(point_data.get("cap", 0)),
            kwh_price=float(point_data.get("costPerKwh", point_data.get("kwhprice", 0.30)))
        )
        db.add(new_point)
        db.commit()
        return new_point

def update_point(db: Session, point_id: str, updates: schemas.PointUpdate):
    # 1. Βρίσκουμε το σημείο
    point = get_point_by_id(db, point_id)
    
    # Αν δεν υπάρχει, επιστρέφουμε None (θα το χειριστεί το main.py)
    if not point:
        return None

    # 2. Ενημερώνουμε ΜΟΝΟ ό,τι μας έστειλε ο χρήστης
    if updates.status is not None:
        point.status = updates.status
        
    if updates.kwhprice is not None:
        point.kwh_price = updates.kwhprice

    # 3. Αποθήκευση
    db.commit()
    db.refresh(point)
    
    return point


# NEW: Create Session (Καταγραφή Φόρτισης & Events)
def create_session(db: Session, session_data: schemas.SessionCreate):
    dt_format = "%Y-%m-%d %H:%M"
    
    try:
        start_dt = datetime.strptime(session_data.starttime, dt_format)
        end_dt = datetime.strptime(session_data.endtime, dt_format)
    except ValueError:
        return None

    # 1. Αποθήκευση του Session
    db_session = models.ChargingSession(
        point_id=session_data.pointid,
        start_time=start_dt,
        end_time=end_dt,
        start_soc=session_data.startsoc,
        end_soc=session_data.endsoc,
        total_kwh=session_data.totalkwh,
        cost_per_kwh=session_data.kwhprice,
        total_amount=session_data.amount
    )
    db.add(db_session)
    
    # 2. Δημιουργία Ιστορικών Events για το status timeline
    # Event Έναρξης: Θεωρούμε ότι ήταν available και έγινε charging
    create_event(db, session_data.pointid, "available", "charging", timestamp=start_dt)
    
    # Event Λήξης: Τελείωσε η φόρτιση, ξαναγίνεται available
    create_event(db, session_data.pointid, "charging", "available", timestamp=end_dt)

    db.commit()
    db.refresh(db_session)
    
    return db_session

# ----------------------------------------------------------------
#  Get Sessions by Date Range
# ----------------------------------------------------------------
def get_sessions_history(db: Session, point_id: str, start_dt: datetime, end_dt: datetime):
    return db.query(models.ChargingSession).filter(
        models.ChargingSession.point_id == point_id,
        models.ChargingSession.start_time >= start_dt,
        models.ChargingSession.start_time < end_dt # Μέχρι και το τέλος της "to" ημέρας
    ).order_by(models.ChargingSession.start_time.desc()).all() # Φθίνουσα ταξινόμηση

# ----------------------------------------------------------------
# NEW: History Logic
# ----------------------------------------------------------------

# Καταγραφή γεγονότος (με υποστήριξη custom timestamp)
def create_event(db: Session, point_id: str, old_status: str, new_status: str, timestamp: datetime = None):
    # Αν δεν δοθεί timestamp, χρησιμοποιούμε την τρέχουσα ώρα (όπως παλιά)
    actual_time = timestamp if timestamp else datetime.now()
    
    event = models.PointEvent(
        point_id=point_id,
        old_state=old_status,
        new_state=new_status,
        event_timestamp=actual_time 
    )
    db.add(event)
    db.commit()
    return event

# Ανάκτηση ιστορικού με φίλτρα ημερομηνίας
def get_point_events(db: Session, point_id: str, start_dt: datetime, end_dt: datetime):
    return db.query(models.PointEvent).filter(
        models.PointEvent.point_id == point_id,
        models.PointEvent.event_timestamp >= start_dt,
        models.PointEvent.event_timestamp < end_dt
    ).order_by(models.PointEvent.event_timestamp.desc()).all() # Φθίνουσα σειρά [cite: 235]



# ----------------------------------------------------------------
# NEW: Bounding Box Logic (Για τον Χάρτη)
# ----------------------------------------------------------------
def get_points_in_bbox(db: Session, ne_lat: float, ne_lon: float, sw_lat: float, sw_lon: float):
    # Φέρνουμε όλα τα σημεία
    all_points = db.query(models.ChargePoint).all()
    visible_points = []
    
    for point in all_points:
        try:
            # Μετατροπή string -> float
            p_lat = float(point.lat)
            p_lon = float(point.lon)
            
            # Έλεγχος: Είναι το σημείο ανάμεσα στο Βόρειο και Νότιο όριο;
            # ΚΑΙ ανάμεσα στο Ανατολικό και Δυτικό όριο;
            if sw_lat <= p_lat <= ne_lat and sw_lon <= p_lon <= ne_lon:
                visible_points.append(point)
                
        except (ValueError, TypeError):
            # Αν κάποιο σημείο έχει σκουπίδια αντί για νούμερα, το αγνοούμε
            continue
            
    return visible_points


def release_expired_reservations(db: Session):
    """
    Βρίσκει σημεία που είναι 'reserved' αλλά πέρασε η ώρα λήξης τους
    και τα γυρίζει σε 'available'.
    """
    now = datetime.now()
    
    # 1. Βρίσκουμε ΜΟΝΟ τα σημεία που είναι reserved ΚΑΙ έχει περάσει η ώρα τους.
    # Αυτό καλύπτει την περίπτωση που ο χρήστης πρόλαβε να ξεκινήσει φόρτιση (status='charging'),
    # καθώς το query θα τα αγνοήσει (αφού ψάχνουμε μόνο status='reserved').
    expired_points = db.query(models.ChargePoint).filter(
        models.ChargePoint.status == "reserved",
        models.ChargePoint.reservation_end_time < now
    ).all()

    released_count = 0
    for point in expired_points:
        # Κρατάμε το παλιό status για το ιστορικό
        old_status = point.status
        
        # Επαναφορά σε available
        point.status = "available"
        point.reservation_end_time = None
        
        # Καταγραφή στο Ιστορικό (σημαντικό!)
        create_event(db, point.point_id, old_status, "available")
        
        released_count += 1

    if released_count > 0:
        db.commit()
        print(f"--- CLEANUP TASK: Released {released_count} expired reservations ---")
