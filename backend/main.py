from fastapi import FastAPI, Depends, HTTPException, APIRouter, Response, Request, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import models, schemas, crud
from database import engine, get_db
import json
import os
import utils 
import csv 
import codecs
import asyncio
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware

# Δημιουργία πινάκων
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- NEW: Ρύθμιση CORS (Για να μιλάει το Frontend με το Backend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Επιτρέπει τα πάντα (για development)
    allow_credentials=True,
    allow_methods=["*"],  # Επιτρέπει GET, POST, PUT, DELETE κλπ
    allow_headers=["*"],
)
# ------------------------------------------------------------------

# Global Exception Handler (500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return utils.create_error_response(
        request=request, status_code=500,
        error_msg="Internal Server Error", debug_info=str(exc)
    )

api_router = APIRouter(prefix="/api")

# --- ΣΤΑΘΕΡΕΣ ---
#  Status Enumeration
VALID_STATUSES = ["available", "charging", "reserved", "malfunction", "offline"]

# [cite: 57] Οι 4 πρώτες υποδηλώνουν ενεργή επικοινωνία
def has_active_communication(status: str) -> bool:
    return status in ["available", "charging", "reserved", "malfunction"]


# ----------------------------------------------------------------
# 1. Login
# ----------------------------------------------------------------
@api_router.post("/login", response_model=schemas.UserShow)
def login(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    """Simple login endpoint - username and password"""
    db_user = db.query(models.User).filter(models.User.username == user_login.username).first()
    
    if not db_user or db_user.password != user_login.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    return db_user

# ----------------------------------------------------------------
# 2. Register (Optional - for convenience)
# ----------------------------------------------------------------
@api_router.post("/register", response_model=schemas.UserShow)
def register(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    """Register a new user"""
    existing_user = db.query(models.User).filter(models.User.username == user_login.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = models.User(username=user_login.username, password=user_login.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ----------------------------------------------------------------
# 3. Healthcheck
# ----------------------------------------------------------------
@api_router.get("/admin/healthcheck", response_model=schemas.HealthCheck)
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        conn_str = str(engine.url)
    except Exception:
        raise Exception("Database connection failed")
    stats = crud.get_stats(db)
    return {
        "status": "OK", "dbconnection": conn_str,
        "n_charge_points": stats["total"], "n_charge_points_online": stats["online"],
        "n_charge_points_offline": stats["offline"]
    }

# ----------------------------------------------------------------
# 4. Reset Points
# ----------------------------------------------------------------
@api_router.post("/admin/resetpoints") 
def reset_points(db: Session = Depends(get_db)):
    try:
        crud.delete_all_points(db)
        file_path = "initial_data.json" 
        if not os.path.exists(file_path):
            raise Exception("initial_data.json file not found")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                crud.create_point(db, item)
        return {"status": "OK", "message": "Points reset successfully"}
    except Exception as e:
        raise e 

# ----------------------------------------------------------------
# 3. Add Points
# ----------------------------------------------------------------
@api_router.post("/admin/addpoints")
async def add_points(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Λίστα με αποδεκτούς τύπους
    valid_mime_types = ['text/csv', 'application/vnd.ms-excel', 'application/csv', 'text/plain', 'application/octet-stream']
    if file.content_type not in valid_mime_types and not file.filename.endswith('.csv'):
        return utils.create_error_response(request=request, status_code=400, error_msg="Invalid file type")

    try:
        csv_reader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
        count = 0
        for row in csv_reader:
            crud.create_point(db, row)
            count += 1
        return {"status": "OK", "imported_points": count}
    except Exception as e:
        raise Exception(f"Failed to import CSV: {str(e)}")

# ----------------------------------------------------------------
# 4. Points List
# ----------------------------------------------------------------
@api_router.get("/points", response_model=list[schemas.PointList])
def read_points(request: Request, status: str = None, format: str = "json", db: Session = Depends(get_db)):
    if status and status not in VALID_STATUSES:
        return utils.create_error_response(request=request, status_code=400, error_msg=f"Invalid status '{status}'")

    points = crud.get_points(db, status=status)
    if not points:
        return Response(status_code=204)

    if format.lower() == 'csv':
        csv_content = utils.to_csv(points, schemas.PointList)
        return Response(content=csv_content, media_type="text/csv")
    
    return points

# ----------------------------------------------------------------
# 5. Point Detail
# ----------------------------------------------------------------
@api_router.get("/point/{id}", response_model=schemas.PointDetail)
def read_point_detail(request: Request, id: str, db: Session = Depends(get_db)):
    point = crud.get_point_by_id(db, point_id=id)
    if not point:
        return utils.create_error_response(request=request, status_code=404, error_msg=f"Point {id} not found")
    return point

# ----------------------------------------------------------------
# 6. Reserve Point 
# ----------------------------------------------------------------

# Κοινή λογική κράτησης
def process_reservation(request: Request, db: Session, point_id: str, minutes: int):
    # 1. Βρίσκουμε το σημείο
    point = crud.get_point_by_id(db, point_id=point_id)
    if not point:
        return utils.create_error_response(request=request, status_code=404, error_msg=f"Point {point_id} not found")

    # 2. Έλεγχος
    if point.status != "available":
        return utils.create_error_response(request=request, status_code=400, error_msg=f"Point is not available")

    # --- NEW: Κρατάμε το παλιό status για το ιστορικό ---
    old_status = point.status 
    # ---------------------------------------------------

    # 3. Υπολογισμός
    max_minutes = int(os.getenv("MAX_RESERVATION_MINUTES", 60))
    duration = min(minutes, max_minutes)
    reservation_end = datetime.now() + timedelta(minutes=duration) 

    # 4. Ενημέρωση
    point.status = "reserved"
    point.reservation_end_time = reservation_end
    db.commit()
    db.refresh(point)

    # --- NEW: Καταγραφή στο Ιστορικό ---
    crud.create_event(db, point.point_id, old_status, "reserved")
    # -----------------------------------

    return point

# Endpoint A: Με χρόνο (/reserve/:id/:minutes)
@api_router.post("/reserve/{id}/{minutes}", response_model=schemas.ReservationResponse)
def reserve_point_with_time(request: Request, id: str, minutes: int, db: Session = Depends(get_db)):
    return process_reservation(request, db, id, minutes)

# Endpoint B: Χωρίς χρόνο (/reserve/:id) -> Default 30'
@api_router.post("/reserve/{id}", response_model=schemas.ReservationResponse)
def reserve_point_default(request: Request, id: str, db: Session = Depends(get_db)):
    return process_reservation(request, db, id, 30) # Default 30 λεπτά 


# ----------------------------------------------------------------
# 7. Update Point 
# ----------------------------------------------------------------
@api_router.post("/updpoint/{id}", response_model=schemas.PointUpdateResponse)
def update_point(
    request: Request,
    id: str,
    updates: schemas.PointUpdate,
    db: Session = Depends(get_db)
):
    if updates.status and updates.status not in VALID_STATUSES:
        return utils.create_error_response(request=request, status_code=400, error_msg=f"Invalid status")

    # --- NEW: Πρέπει να βρούμε το σημείο ΠΡΙΝ το update για να ξέρουμε το παλιό status ---
    point = crud.get_point_by_id(db, point_id=id)
    if not point:
         return utils.create_error_response(request=request, status_code=404, error_msg=f"Point not found")
    
    old_status = point.status
    # -------------------------------------------------------------------------------------

    updated_point = crud.update_point(db, point_id=id, updates=updates)

    # --- NEW: Αν άλλαξε το status, γράφουμε ιστορικό ---
    if updates.status and old_status != updates.status:
        crud.create_event(db, id, old_status, updates.status)
    # ---------------------------------------------------

    return updated_point

# ----------------------------------------------------------------
# 8. Create Session (New Charging Event) [cite: 145-149]
# ----------------------------------------------------------------
@api_router.post("/newsession")
def create_session_endpoint(
    request: Request,
    session_data: schemas.SessionCreate,
    db: Session = Depends(get_db)
):
    # 1. Έλεγχος αν υπάρχει το point_id
    point = crud.get_point_by_id(db, point_id=session_data.pointid)
    if not point:
        return utils.create_error_response(
            request=request,
            status_code=404,
            error_msg=f"Point with ID {session_data.pointid} not found"
        )

    # 2. Αποθήκευση
    new_session = crud.create_session(db, session_data)
    
    # 3. Έλεγχος για λάθος format ημερομηνίας (αν το crud επέστρεψε None)
    if not new_session:
        return utils.create_error_response(
            request=request,
            status_code=400,
            error_msg="Invalid date format. Expected 'YYYY-MM-DD HH:MM'"
        )

    # 4. Επιτυχία: Επιστροφή κενού body 
    return {}


# ----------------------------------------------------------------
# 9. Charging Sessions History 
# ----------------------------------------------------------------
@api_router.get("/sessions/{id}/{from_date}/{to_date}", response_model=list[schemas.SessionShow])
def get_sessions_history(
    request: Request,
    id: str,
    from_date: str, # Path param as String YYYYMMDD
    to_date: str,   # Path param as String YYYYMMDD
    format: str = "json",
    db: Session = Depends(get_db)
):
    # 1. Parsing Ημερομηνιών (YYYYMMDD -> datetime)
    try:
        start_dt = datetime.strptime(from_date, "%Y%m%d")
        
        # Για την ημερομηνία λήξης, προσθέτουμε 1 μέρα για να πιάσουμε όλο το 24ωρο
        # Π.χ. Αν to_date="20250101", ψάχνουμε μέχρι < "20250102 00:00"
        end_dt_input = datetime.strptime(to_date, "%Y%m%d")
        end_dt = end_dt_input + timedelta(days=1)
        
    except ValueError:
        return utils.create_error_response(
            request=request, 
            status_code=400, 
            error_msg="Invalid date format. Expected YYYYMMDD"
        )

    # 2. Έλεγχος αν υπάρχει το σημείο (Προαιρετικό, αλλά καλό για UX)
    # Το PDF δεν το απαιτεί ρητά εδώ, αλλά αν το ID δεν υπάρχει, η λίστα θα είναι κενή (σωστό).
    # Αν θέλουμε να είμαστε αυστηροί με το 404:
    if not crud.get_point_by_id(db, point_id=id):
        return utils.create_error_response(
            request=request, 
            status_code=404, 
            error_msg=f"Point {id} not found"
        )

    # 3. Αναζήτηση
    sessions = crud.get_sessions_history(db, point_id=id, start_dt=start_dt, end_dt=end_dt)

    # 4. Χειρισμός Κενής Λίστας (204 No Content)
    if not sessions:
        return Response(status_code=204)

    # 5. CSV Support (αφού επιστρέφει λίστα)
    if format.lower() == 'csv':
        csv_content = utils.to_csv(sessions, schemas.SessionShow)
        return Response(content=csv_content, media_type="text/csv")

    return sessions


# ----------------------------------------------------------------
# 10. Point Status History [cite: 202-204]
# ----------------------------------------------------------------
@api_router.get("/pointstatus/{id}/{from_date}/{to_date}", response_model=list[schemas.PointEventShow])
def get_point_status_history(
    request: Request,
    id: str,
    from_date: str,
    to_date: str,
    format: str = "json",
    db: Session = Depends(get_db)
):
    # 1. Parsing Ημερομηνιών
    try:
        start_dt = datetime.strptime(from_date, "%Y%m%d")
        end_dt_input = datetime.strptime(to_date, "%Y%m%d")
        end_dt = end_dt_input + timedelta(days=1)
    except ValueError:
        return utils.create_error_response(request=request, status_code=400, error_msg="Invalid date format. Expected YYYYMMDD")

    # 2. Αναζήτηση
    events = crud.get_point_events(db, point_id=id, start_dt=start_dt, end_dt=end_dt)

    # 3. Χειρισμός Κενής Λίστας
    if not events:
        return Response(status_code=204)

    # 4. CSV Support
    if format.lower() == 'csv':
        csv_content = utils.to_csv(events, schemas.PointEventShow)
        return Response(content=csv_content, media_type="text/csv")
    
    return events

# ----------------------------------------------------------------
# 11. Get Points in Bounding Box (Για τον Χάρτη)
# ----------------------------------------------------------------
@api_router.get("/points/bbox", response_model=list[schemas.PointDetail])
def get_points_bbox(
    ne_lat: float, 
    ne_lon: float, 
    sw_lat: float, 
    sw_lon: float, 
    db: Session = Depends(get_db)
):
    # Καλούμε τη συνάρτηση που φτιάξαμε στο CRUD
    return crud.get_points_in_bbox(db, ne_lat, ne_lon, sw_lat, sw_lon)

async def cleanup_expired_reservations():
    """Τρέχει κάθε 60 δευτερόλεπτα και ελευθερώνει ληγμένες κρατήσεις."""
    while True:
        try:
            # Περιμένουμε 60 δευτερόλεπτα πριν τον επόμενο έλεγχο
            await asyncio.sleep(60)
            
            # Δημιουργούμε νέο DB session
            db = next(get_db()) 
            crud.release_expired_reservations(db)
            db.close() # Κλείνουμε το session χειροκίνητα
            
        except Exception as e:
            print(f"Error in cleanup task: {e}")

@app.on_event("startup")
async def startup_event():
    # Ξεκινάει το task στο παρασκήνιο μόλις ανοίξει ο server
    asyncio.create_task(cleanup_expired_reservations())


app.include_router(api_router)  #this is always the last line in the file!
