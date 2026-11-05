from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from datetime import datetime

# --- Βοηθητική συνάρτηση ---
def format_dt(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%d %H:%M') 

# ---------------------------------------------------------------------------
# 1. USER SCHEMAS
# ---------------------------------------------------------------------------
class UserLogin(BaseModel):
    username: str
    password: str

class UserShow(BaseModel):
    username: str
    role: str
    class Config:
        from_attributes = True

# ---------------------------------------------------------------------------
# 2. CHARGE POINT SCHEMAS
# ---------------------------------------------------------------------------

# 1. Base: Fields shared by EVERYONE
class PointBase(BaseModel):
    pointid: str = Field(..., validation_alias="point_id")       
    lon: str
    lat: str
    status: str
    cap: int

    class Config:
        from_attributes = True
        populate_by_name = True 

# 2. List Schema: Used for the strict /points endpoint
# PDF Requirement: Needs providerName, MUST NOT have kwhprice
class PointList(BaseModel):
    # 1. First Field (as requested)
    providerName: str = Field("bestPowerGR", validation_alias="provider_name") 
    
    # 2. Other Fields (repeated manually to ensure order)
    pointid: str = Field(..., validation_alias="point_id")       
    lon: str
    lat: str
    status: str
    cap: int

    class Config:
        from_attributes = True
        populate_by_name = True 

# 3. Detail Schema: Used for /point/:id AND your Map (/points/bbox)
# PDF Requirement: Needs kwhprice, MUST NOT have providerName
class PointDetail(PointBase):
    reservationendtime: Optional[datetime] = Field(None, validation_alias="reservation_end_time")
    kwhprice: Optional[float] = Field(None, validation_alias="kwh_price")

    @field_serializer('reservationendtime')
    def serialize_res_time(self, v: datetime, _info):
        return format_dt(v)

# ---------------------------------------------------------------------------
# 3. SESSION SCHEMAS
# ---------------------------------------------------------------------------
class SessionCreate(BaseModel):
    pointid: str = Field(..., alias="id") 
    starttime: str 
    endtime: str
    startsoc: int
    endsoc: int
    totalkwh: float
    kwhprice: float
    amount: float = Field(..., alias="Amount") 

class SessionShow(BaseModel):
    # ΔΙΟΡΘΩΣΗ: Αλλάξαμε το type hint από str σε datetime
    # Έτσι το Pydantic δέχεται το αντικείμενο από τη βάση χωρίς να "σκάει".
    starttime: datetime = Field(..., validation_alias="start_time")
    endtime: datetime = Field(..., validation_alias="end_time")
    
    startsoc: int = Field(..., validation_alias="start_soc")
    endsoc: int = Field(..., validation_alias="end_soc")
    totalkwh: float = Field(..., validation_alias="total_kwh")
    kwhprice: float = Field(..., validation_alias="cost_per_kwh") 
    amount: float = Field(..., validation_alias="total_amount")   

    class Config:
        from_attributes = True

    # Ο serializer παίρνει το datetime και το κάνει String για το JSON
    @field_serializer('starttime')
    def serialize_start(self, v: datetime, _info):
        return format_dt(v)

    @field_serializer('endtime')
    def serialize_end(self, v: datetime, _info):
        return format_dt(v)

# ---------------------------------------------------------------------------
# 4. ADMIN SCHEMAS
# ---------------------------------------------------------------------------
class HealthCheck(BaseModel):
    status: str
    dbconnection: str
    n_charge_points: int
    n_charge_points_online: int
    n_charge_points_offline: int

# ---------------------------------------------------------------------------
# 5. ERROR LOG SCHEMA
# ---------------------------------------------------------------------------
class ErrorLog(BaseModel):
    call: str
    timeref: str
    originator: str
    return_code: int = Field(..., alias="return_code") 
    error: str
    debuginfo: Optional[str] = None

# ---------------------------------------------------------------------------
# 6. RESERVATION SCHEMA
# ---------------------------------------------------------------------------
class ReservationResponse(BaseModel):
    pointid: str = Field(..., validation_alias="point_id")
    status: str
    reservationendtime: Optional[datetime] = Field(None, validation_alias="reservation_end_time")

    class Config:
        from_attributes = True

    @field_serializer('reservationendtime')
    def serialize_res_time(self, v: datetime, _info):
        return format_dt(v)

# ---------------------------------------------------------------------------
# 7. UPDATE POINT SCHEMAS
# ---------------------------------------------------------------------------
class PointUpdate(BaseModel):
    status: Optional[str] = None
    kwhprice: Optional[float] = None 

class PointUpdateResponse(BaseModel):
    pointid: str = Field(..., validation_alias="point_id")
    status: str
    kwhprice: Optional[float] = Field(None, validation_alias="kwh_price")

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 8. POINT STATUS HISTORY 
# ---------------------------------------------------------------------------
class PointEventShow(BaseModel):
    # validation_alias = Πώς το λένε στη βάση (Python)
    # serialization_alias = Πώς το θέλει το JSON (PDF)
    
    timeref: datetime = Field(..., validation_alias="event_timestamp")
    
    old_state: str = Field(..., 
                           validation_alias="old_state") 
    
    new_state: str = Field(..., 
                           validation_alias="new_state")

    class Config:
        from_attributes = True

    @field_serializer('timeref')
    def serialize_timeref(self, v: datetime, _info):
        return format_dt(v)        