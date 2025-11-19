import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import create_document, get_documents, db
from schemas import User, Clinic, DoctorProfile, AvailabilitySlot, Appointment, Invoice, Payment, InvoiceItem

app = FastAPI(title="Clinic Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Clinic Management API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# ----------------------------- Users & Clinics -----------------------------
@app.post("/users", response_model=dict)
def create_user(user: User):
    inserted_id = create_document("user", user)
    return {"id": inserted_id}

@app.get("/users", response_model=List[dict])
def list_users():
    return get_documents("user")

@app.post("/clinics", response_model=dict)
def create_clinic(clinic: Clinic):
    inserted_id = create_document("clinic", clinic)
    return {"id": inserted_id}

@app.get("/clinics", response_model=List[dict])
def list_clinics():
    return get_documents("clinic")

# ----------------------------- Doctors & Availability -----------------------------
@app.post("/doctors", response_model=dict)
def create_doctor(profile: DoctorProfile):
    inserted_id = create_document("doctorprofile", profile)
    return {"id": inserted_id}

@app.get("/doctors", response_model=List[dict])
def list_doctors():
    return get_documents("doctorprofile")

@app.post("/availability", response_model=dict)
def add_availability(slot: AvailabilitySlot):
    inserted_id = create_document("availabilityslot", slot)
    return {"id": inserted_id}

@app.get("/availability/{doctor_id}", response_model=List[dict])
def get_availability(doctor_id: str):
    return get_documents("availabilityslot", {"doctor_id": doctor_id})

# ----------------------------- Appointments -----------------------------
class AppointmentRequest(BaseModel):
    clinic_id: str
    doctor_id: str
    patient_id: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    duration_minutes: int = 30
    reason: Optional[str] = None

@app.post("/appointments", response_model=dict)
def create_appointment(req: AppointmentRequest):
    # Build datetime objects
    try:
        starts_at = datetime.strptime(f"{req.date} {req.start_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format")
    ends_at = starts_at + timedelta(minutes=req.duration_minutes)

    # Basic overlap check
    existing = get_documents("appointment", {
        "doctor_id": req.doctor_id,
        "starts_at": {"$lt": ends_at},
        "ends_at": {"$gt": starts_at}
    })
    if existing:
        raise HTTPException(status_code=409, detail="overlap")

    appt = Appointment(
        clinic_id=req.clinic_id,
        doctor_id=req.doctor_id,
        patient_id=req.patient_id,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=req.reason,
    )
    inserted_id = create_document("appointment", appt)
    return {"id": inserted_id}

@app.get("/appointments", response_model=List[dict])
def list_appointments(clinic_id: Optional[str] = None, doctor_id: Optional[str] = None, patient_id: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None):
    query: dict = {}
    if clinic_id:
        query["clinic_id"] = clinic_id
    if doctor_id:
        query["doctor_id"] = doctor_id
    if patient_id:
        query["patient_id"] = patient_id
    if from_date or to_date:
        date_filter: dict = {}
        if from_date:
            date_filter["$gte"] = datetime.strptime(from_date, "%Y-%m-%d")
        if to_date:
            # include entire day
            date_filter["$lte"] = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
        query["starts_at"] = date_filter
    return get_documents("appointment", query)

# ----------------------------- Billing -----------------------------
class InvoiceCreateRequest(BaseModel):
    clinic_id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    items: List[InvoiceItem]
    discount: float = 0.0
    tax_rate: float = 0.0

@app.post("/invoices", response_model=dict)
def create_invoice(req: InvoiceCreateRequest):
    invoice = Invoice(
        clinic_id=req.clinic_id,
        appointment_id=req.appointment_id,
        patient_id=req.patient_id,
        doctor_id=req.doctor_id,
        items=req.items,
        discount=req.discount,
        tax_rate=req.tax_rate,
    )
    inserted_id = create_document("invoice", invoice)
    return {"id": inserted_id}

@app.get("/invoices", response_model=List[dict])
def list_invoices(clinic_id: Optional[str] = None, status: Optional[str] = None):
    query: dict = {}
    if clinic_id:
        query["clinic_id"] = clinic_id
    if status:
        query["status"] = status
    return get_documents("invoice", query)

@app.post("/payments", response_model=dict)
def record_payment(payment: Payment):
    inserted_id = create_document("payment", payment)
    return {"id": inserted_id}

@app.get("/payments", response_model=List[dict])
def list_payments(clinic_id: Optional[str] = None, invoice_id: Optional[str] = None):
    query: dict = {}
    if clinic_id:
        query["clinic_id"] = clinic_id
    if invoice_id:
        query["invoice_id"] = invoice_id
    return get_documents("payment", query)

# ----------------------------- Analytics -----------------------------
@app.get("/analytics/summary", response_model=dict)
def analytics_summary(clinic_id: str, period: str = "month", date: Optional[str] = None):
    # period: day | week | month
    # For demo purposes, we will compute basic aggregates client-side using fetched docs.
    # Here, just return lists the frontend can aggregate, to keep server simple.
    appts = get_documents("appointment", {"clinic_id": clinic_id})
    invoices = get_documents("invoice", {"clinic_id": clinic_id})
    payments = get_documents("payment", {"clinic_id": clinic_id})
    return {"appointments": appts, "invoices": invoices, "payments": payments}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
