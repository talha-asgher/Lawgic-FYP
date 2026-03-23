# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime


# ── Auth / User ───────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone_num: Optional[str] = None
    role: str


class UserCreate(UserBase):
    password: str


class UserOut(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    phone_num: Optional[str] = None
    role: str
    is_active: bool
    profile_image_url: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    """Token response — includes nested user object for frontend routing."""
    access_token: str
    token_type: str
    user: UserOut


class UserProfileOut(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    phone_num: Optional[str] = None
    role: str
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone_num: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ── Lawyer Profile ────────────────────────────────────────────────────────────

class LawyerProfileCreate(BaseModel):
    specialization: str               # comma-separated for multi e.g. "Criminal Law,Family Law"
    bio_data: Optional[str] = None
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    consultation_fee: Optional[float] = None
    city: Optional[str] = None
    languages: Optional[str] = None  # comma-separated e.g. "Urdu,English"
    bar_council_number: Optional[str] = None
    law_school: Optional[str] = None
    grad_year: Optional[int] = None
    degree_type: Optional[str] = None


class LawyerProfileOut(BaseModel):
    lawyer_id: int
    specialization: str
    bio_data: Optional[str] = None
    verification_status: str
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    consultation_fee: Optional[float] = None
    city: Optional[str] = None
    languages: Optional[str] = None
    bar_council_number: Optional[str] = None
    law_school: Optional[str] = None
    grad_year: Optional[int] = None
    degree_type: Optional[str] = None
    average_rating: Optional[float] = None
    review_count: int = 0

    class Config:
        from_attributes = True


class LawyerPublic(BaseModel):
    lawyer_id: int
    name: str
    email: Optional[str] = None
    phone_num: Optional[str] = None
    specialization: str
    specializations: List[str] = []
    bio_data: Optional[str] = None
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    city: Optional[str] = None
    consultation_fee: Optional[float] = None
    verification_status: str
    languages: Optional[str] = None
    languages_list: List[str] = []
    average_rating: Optional[float] = None
    review_count: int = 0
    bar_council_number: Optional[str] = None
    degree_type: Optional[str] = None
    law_school: Optional[str] = None

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


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    lawyer_id: int
    stars: int
    comment: Optional[str] = None

    @field_validator("stars")
    @classmethod
    def validate_stars(cls, v):
        if v < 1 or v > 5:
            raise ValueError("Stars must be between 1 and 5")
        return v


class ReviewOut(BaseModel):
    rating_id: int
    user_id: int
    lawyer_id: int
    stars: int
    comment: Optional[str] = None
    reviewer_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Legal Institutions ────────────────────────────────────────────────────────

class LegalInstitutionOut(BaseModel):
    inst_id: int
    osm_id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    amenity: Optional[str] = None
    office: Optional[str] = None
    address: Optional[str] = None
    jurisdiction: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


# ── Appointments ──────────────────────────────────────────────────────────────

class AppointmentCreate(BaseModel):
    mode_of_comm: str
    scheduled_at: datetime
    lawyer_id: int
    notes: Optional[str] = None


class AppointmentOut(BaseModel):
    appt_id: int
    mode_of_comm: str
    scheduled_at: datetime
    status: str
    notes: Optional[str] = None
    user_id: int
    lawyer_id: int
    lawyer_name: Optional[str] = None
    client_name: Optional[str] = None

    class Config:
        from_attributes = True


class AppointmentStatusUpdate(BaseModel):
    status: str


# ── Cases ─────────────────────────────────────────────────────────────────────

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
    client_name: Optional[str] = None
    assigned_lawyer_name: Optional[str] = None

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
    case_title: Optional[str] = None
    client_name: Optional[str] = None

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


# ── Case Messages (in-case chat) ──────────────────────────────────────────────

class CaseMessageCreate(BaseModel):
    content: str


class CaseMessageOut(BaseModel):
    message_id: int
    case_id: int
    sender_id: int
    sender_name: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ── Direct Messaging / Conversations ─────────────────────────────────────────

class ConversationCreate(BaseModel):
    other_user_id: int
    title: Optional[str] = Field(None, max_length=150)
    initial_message: Optional[str] = Field(None, max_length=2000)

    @field_validator("initial_message")
    @classmethod
    def initial_message_not_blank(cls, v):
        if v is not None:
            if not v.strip():
                raise ValueError("Initial message cannot be blank")
            return v.strip()
        return v


class ConversationParticipantOut(BaseModel):
    user_id: int
    name: str

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    conv_id: int
    title: Optional[str] = None
    participants: List[ConversationParticipantOut] = []
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str = Field(..., max_length=2000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v):
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message content cannot be empty")
        return stripped


class MessageOut(BaseModel):
    message_id: int
    conv_id: int
    sender_id: int
    sender_name: Optional[str] = None
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Documents / Templates ─────────────────────────────────────────────────────

class DocumentTemplateOut(BaseModel):
    template_id: int
    type: str
    language: str
    title: Optional[str] = None
    description: Optional[str] = None
    fields_schema: Optional[str] = None  # JSON string

    class Config:
        from_attributes = True


class DocumentGenerateRequest(BaseModel):
    template_id: int
    title: str
    input_data: Optional[Dict[str, Any]] = None  # field values from the form


class DocumentOut(BaseModel):
    doc_id: int
    user_id: int
    template_id: Optional[int] = None
    title: str
    type: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Document Analysis ─────────────────────────────────────────────────────────

class DocAnalysisOut(BaseModel):
    analysis_id: int
    user_id: int
    file_name: Optional[str] = None
    status: str
    summary: Optional[str] = None
    risks: Optional[str] = None        # JSON string — parsed on FE
    key_details: Optional[str] = None  # JSON string
    created_at: datetime

    class Config:
        from_attributes = True


# ── Ask AI / Q&A ─────────────────────────────────────────────────────────────

class AskAIRequest(BaseModel):
    question: str
    language: str = "en"
    session_id: Optional[str] = None  # groups questions into one chat session


class CitationOut(BaseModel):
    source_title: Optional[str] = None
    citation_ref: Optional[str] = None
    snippet_text: Optional[str] = None


class AskAIResponse(BaseModel):
    qa_id: int
    question: str
    answer: Optional[str] = None
    language: str
    status: str    # pending | answered | failed
    session_id: Optional[str] = None
    citations: List[CitationOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ── Inheritance Calculator ────────────────────────────────────────────────────

class HeirInput(BaseModel):
    deceased_gender: str          # "male" or "female"
    spouse_count: int = 0         # wives (if male) or husband (if female, max 1)
    sons: int = 0
    daughters: int = 0
    father_alive: bool = False
    mother_alive: bool = False
    grandfather_alive: bool = False
    grandmother_alive: bool = False
    full_brothers: int = 0
    full_sisters: int = 0
    estate_value: Optional[float] = None  # PKR, optional for % only mode


class HeirShare(BaseModel):
    heir: str
    fraction: str     # e.g. "1/2", "1/8"
    percentage: float
    amount: Optional[float] = None   # only if estate_value provided


class InheritanceResult(BaseModel):
    shares: List[HeirShare]
    total_percentage: float
    notes: List[str] = []


# ── Dashboard ─────────────────────────────────────────────────────────────────

class UserDashboardStats(BaseModel):
    documents: int = 0
    qa_sessions: int = 0
    appointments: int = 0
    open_cases: int = 0
    unread_messages: int = 0


class LawyerDashboardStats(BaseModel):
    active_cases: int = 0
    pending_requests: int = 0
    appointments_this_week: int = 0
    total_reviews: int = 0
    average_rating: float = 0.0
    unread_messages: int = 0
