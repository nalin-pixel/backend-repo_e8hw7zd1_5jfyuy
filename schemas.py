"""
Database Schemas for Clinic Management App

Each Pydantic model maps to a MongoDB collection (lowercased class name).
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

# Core actors
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    role: Literal["admin", "doctor", "patient"] = Field(...)
    clinic_id: Optional[str] = Field(None, description="Clinic this user belongs to (for admin/doctor)")
    phone: Optional[str] = None
    is_active: bool = True

class Clinic(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    owner_user_id: Optional[str] = None

class DoctorProfile(BaseModel):
    user_id: str = Field(..., description="Reference to user with role=doctor")
    clinic_id: str
    specialty: Optional[str] = None
    bio: Optional[str] = None
    fee: float = 0.0

class AvailabilitySlot(BaseModel):
    doctor_id: str
    clinic_id: str
    weekday: int = Field(..., ge=0, le=6, description="0=Mon .. 6=Sun")
    start_time: str = Field(..., description="Start time in HH:MM")
    end_time: str = Field(..., description="End time in HH:MM")

class Appointment(BaseModel):
    clinic_id: str
    doctor_id: str
    patient_id: str
    starts_at: datetime
    ends_at: datetime
    reason: Optional[str] = None
    status: Literal["scheduled", "checked_in", "completed", "cancelled"] = "scheduled"

class InvoiceItem(BaseModel):
    name: str
    qty: int = 1
    unit_price: float = 0.0

class Invoice(BaseModel):
    clinic_id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    items: List[InvoiceItem] = []
    discount: float = 0.0
    tax_rate: float = 0.0
    status: Literal["unpaid", "paid", "void"] = "unpaid"

class Payment(BaseModel):
    clinic_id: str
    invoice_id: str
    amount: float
    method: Literal["cash", "card", "transfer", "insurance"] = "cash"
    notes: Optional[str] = None
