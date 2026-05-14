# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime

from app.services.language_output import normalize_output_language as _norm_out_lang



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
    access_token: str
    token_type: str
    user: UserOut


class UserProfileOut(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    phone_num: Optional[str] = None
    city: Optional[str] = None
    role: str
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone_num: Optional[str] = None
    city: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str





class LawyerProfileCreate(BaseModel):
    specialization: str               # Criminal Law,Family Law, etc.
    bio_data: Optional[str] = None
    years_of_experience: Optional[int] = None
    office_address: Optional[str] = None
    consultation_fee: Optional[float] = None
    city: Optional[str] = None
    languages: Optional[str] = None  # Urdu,English
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
    lawyer_name: Optional[str] = None
    case_description: Optional[str] = None
    case_law_domain: Optional[str] = None

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
    sender_name: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime

    class Config:
        from_attributes = True





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

class DocumentAnalysisResult(BaseModel):
    document_type: str = ""
    summary: str = ""
    disclaimer: str = ""


def document_analysis_from_stored_dict(data: dict) -> DocumentAnalysisResult:
    """Build the slim result; merge legacy array fields into summary when needed."""
    disclaimer = (
        str(data.get("disclaimer") or "").strip()
        or "This is AI-generated legal assistance and not a substitute for professional legal advice."
    )
    doc_type = str(data.get("document_type") or "").strip() or "Unknown"
    summary = str(data.get("summary") or "").strip()

    if not summary:
        blocks: list[str] = []
        pairs = [
            ("Overview / key points", "key_clauses"),
            ("Missing or unclear information", "missing_information"),
            ("Risks or red flags", "risks"),
            ("Suggestions", "suggestions"),
        ]
        for title, key in pairs:
            arr = data.get(key)
            if isinstance(arr, list) and arr:
                lines = "\n".join(f"• {str(x).strip()}" for x in arr if str(x).strip())
                if lines:
                    blocks.append(f"{title}\n{lines}")
        if data.get("legal_references") and isinstance(data["legal_references"], list):
            ref_lines = []
            for ref in data["legal_references"][:5]:
                if not isinstance(ref, dict):
                    continue
                act = str(ref.get("act_name") or "").strip()
                reason = str(ref.get("reason") or "").strip()
                if act or reason:
                    ref_lines.append(
                        f"• {act}"
                        + (f" ({reason})" if reason else "")
                    )
            if ref_lines:
                blocks.append("Legal references (verify independently)\n" + "\n".join(ref_lines))
        summary = "\n\n".join(blocks).strip()

    return DocumentAnalysisResult(
        document_type=doc_type,
        summary=summary or "—",
        disclaimer=disclaimer,
    )


class DocAnalysisOut(BaseModel):
    analysis_id: int
    user_id: int
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    output_language: str = Field(
        default="en",
        description="Analysis output language: en | ur (Arabic script). Legacy codes map to ur.",
    )
    status: str
    progress_stage: Optional[str] = None
    summary: Optional[str] = None
    risks: Optional[str] = None
    key_details: Optional[str] = None
    result: Optional[DocumentAnalysisResult] = None
    created_at: datetime

    @field_validator("output_language", mode="before")
    @classmethod
    def _normalize_doc_output_language(cls, v: object) -> str:
        return _norm_out_lang(v)

    class Config:
        from_attributes = True


class DocAnalysisCreatedOut(DocAnalysisOut):
    from_cache: bool = False







class AskAIRequest(BaseModel):
    question: str
    language: str = "en"
    session_id: Optional[str] = None  # groups questions into one chat session
    query_language: Optional[str] = Field(
        default=None,
        description="Same as RagAskRequest.query_language: optional auto | en | ur for retrieval translation.",
    )

    @field_validator("language", mode="before")
    @classmethod
    def _normalize_ask_ai_language(cls, v: object) -> str:
        return _norm_out_lang(v)


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


class RagAskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    act_name: Optional[str] = None
    category: Optional[str] = None
    section_number: Optional[str] = None
    top_k_retrieval: int = 15
    top_k_context: int = 6
    search_tables: Optional[bool] = None
    search_forms: Optional[bool] = None
    output_language: str = Field(
        default="en",
        description=(
            "Legacy field; chat responses follow the query language (Urdu script / query_language vs English). "
            "Kept for API compatibility. Values: en | ur."
        ),
    )
    query_language: Optional[str] = Field(
        default=None,
        description=(
            "Optional hint for the user query: auto (default), en, ur. "
            "When ur or Urdu Arabic script under auto, the query is translated to English "
            "for embedding, lexical search, reranking, and the SLM prompt (main pipeline stays English)."
        ),
    )

    @field_validator("output_language", mode="before")
    @classmethod
    def _normalize_rag_ask_output_language(cls, v: object) -> str:
        return _norm_out_lang(v)


class RagSourceOut(BaseModel):
    """One retrieved passage for display as a source (UI: collapsed metadata + optional full text)."""
    source_index: int = Field(..., ge=1, description="Matches [n] in grounded context and model output")
    act_name: Optional[str] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    page_numbers: Optional[List[Any]] = None
    chunk_type: Optional[str] = None
    object_id: Optional[str] = None
    source_reference: Optional[str] = Field(
        default=None,
        description="Human-readable pointer, e.g. Section X — title",
    )
    excerpt_text: Optional[str] = Field(default=None, description="Short excerpt; use full_source_text when expanded")
    full_source_text: Optional[str] = Field(default=None, description="Full chunk text for expanded source view")


class RetrievedChunkOut(BaseModel):
    chunk_type: str
    object_id: str
    parent_id: Optional[str] = None
    act_name: Optional[str] = None
    category: Optional[str] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    page_numbers: Optional[List[Any]] = None
    score: float = 0.0
    rerank_score: Optional[float] = None
    summary: Optional[str] = None
    text: str = ""


class RagAskResponse(BaseModel):
    answer: str
    insufficient_context: bool = False
    low_retrieval_confidence: bool = False
    output_language: str = Field(
        default="en",
        description="en | ur — follows the user's query language (see finalize_rag_ask rules).",
    )
    used_source_indexes: List[int] = Field(default_factory=list)
    used_source_ids: List[str] = Field(default_factory=list)
    confidence_score: float
    confidence_label: str
    sources: List[RagSourceOut] = Field(
        default_factory=list,
        description="Passages the model reported using (filtered by used_source_indexes / used_source_ids)",
    )
    retrieved_sources: List[RagSourceOut] = Field(
        default_factory=list,
        description="All deduped context sources when the model did not report any used indexes or ids",
    )
    retrieved_chunks: List[RetrievedChunkOut] = Field(default_factory=list)
    retrieval_meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("output_language", mode="before")
    @classmethod
    def _normalize_rag_response_language(cls, v: object) -> str:
        return _norm_out_lang(v)


# ── Inheritance Calculator ────────────────────────────────────────────────────



class HeirInput(BaseModel):
    deceased_gender: str          # "male" or "female"
    spouse_count: int = 0
    sons: int = 0
    daughters: int = 0
    father_alive: bool = False
    mother_alive: bool = False
    grandfather_alive: bool = False
    grandmother_alive: bool = False
    full_brothers: int = 0
    full_sisters: int = 0
    estate_value: Optional[float] = None


class HeirShare(BaseModel):
    heir: str
    fraction: str
    percentage: float
    amount: Optional[float] = None


class InheritanceResult(BaseModel):
    shares: List[HeirShare]
    total_percentage: float
    notes: List[str] = []





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
