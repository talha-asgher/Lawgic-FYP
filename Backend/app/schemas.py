# app/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone_num: Optional[str] = None
    role: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    user_id: int

    class Config:
        
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfileOut(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    phone_num: Optional[str] = None
    role: str

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone_num: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class LawyerProfileBase(BaseModel):
    specialization: str
    bio_data: Optional[str] = None
    #verification_status: str = "pending"
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    consultation_fee: Optional[float] = None


class LawyerProfileCreate(LawyerProfileBase):

    pass


class LawyerProfileOut(LawyerProfileBase):
    lawyer_id: int

    class Config:
        from_attributes = True


class LawyerPublic(BaseModel):
    lawyer_id: int
    name: str
    specialization: str
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    consultation_fee: Optional[float] = None
    verification_status: str

    class Config:
        from_attributes = True


class LegalInstitutionOut(BaseModel):
    inst_id: int
    osm_id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    amenity: Optional[str] = None
    office: Optional[str] = None
    address: Optional[str] = None
    jurisdiction: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class AppointmentCreate(BaseModel):
    mode_of_comm: str
    scheduled_at: datetime
    lawyer_id: int


class AppointmentOut(BaseModel):
    appt_id: int
    mode_of_comm: str
    scheduled_at: datetime
    status: str
    user_id: int
    lawyer_id: int

    class Config:
        from_attributes = True

class AppointmentStatusUpdate(BaseModel):
    status: str 


class CaseCreate(BaseModel):
    title: str
    description: str
    law_domain: str
    jurisdiction: Optional[str] = None
    lawyer_ids: Optional[List[int]] = None 


class CaseOut(BaseModel):
    case_id: int
    user_id: int
    title: str
    description: str
    law_domain: str
    jurisdiction: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseStatusUpdate(BaseModel):
    status: str


class CaseRequestOut(BaseModel):
    request_id: int
    case_id: int
    lawyer_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseAssignmentOut(BaseModel):
    assignment_id: int
    case_id: int
    lawyer_id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RequestResponse(BaseModel):
    status: str

class CaseMessageCreate(BaseModel):
    content: str


class CaseMessageOut(BaseModel):
    message_id: int
    case_id: int
    sender_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class LawyerRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone_num: Optional[str] = None

    specialization: str
    bio_data: Optional[str] = None
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    consultation_fee: Optional[float] = None