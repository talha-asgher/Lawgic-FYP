from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
    LargeBinary,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(Text, unique=True, nullable=False, index=True)
    name = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    phone_num = Column(Text, nullable=True)
    role = Column(Text, nullable=False)  # 'client' or 'lawyer'
    is_active = Column(Boolean, default=True)
    profile_image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    lawyer_profile = relationship("LawyerProfile", back_populates="user", uselist=False)
    documents = relationship("Document", back_populates="user")
    complaints = relationship("Complaint", back_populates="user")
    qa_interactions = relationship("QAInteraction", back_populates="user")
    ratings_given = relationship("RatingReview", back_populates="user")
    cases = relationship("Case", back_populates="user")
    requests = relationship("Request", back_populates="user")
    appointments = relationship("Appointment", back_populates="user")
    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")
    conversation_participants = relationship("ConversationParticipant", back_populates="user")


class LawyerProfile(Base):
    __tablename__ = "lawyer_profiles"

    lawyer_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    specialization = Column(Text, nullable=False)
    bio_data = Column(Text, nullable=True)
    verification_status = Column(Text, nullable=False, default="pending")
    years_of_experience = Column(Integer, nullable=True)
    office_address = Column(Text, nullable=True)
    consultation_fee = Column(Numeric, nullable=True)
    city = Column(Text, nullable=True)
    languages = Column(Text, nullable=True)
    bar_council_number = Column(Text, nullable=True)
    law_school = Column(Text, nullable=True)
    grad_year = Column(Integer, nullable=True)
    degree_type = Column(Text, nullable=True)
    average_rating = Column(Float, nullable=True, default=0.0)
    review_count = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="lawyer_profile")
    assignments = relationship("CaseAssignment", back_populates="lawyer_profile", cascade="all, delete-orphan")
    requests = relationship("Request", back_populates="lawyer_profile", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="lawyer")
    reviews = relationship("RatingReview", back_populates="lawyer_profile", foreign_keys="RatingReview.lawyer_id")


class LegalSource(Base):
    __tablename__ = "legal_sources"

    source_id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    jurisdiction = Column(Text, nullable=True)
    citation_ref = Column(Text, nullable=True)

    qa_citations = relationship("QACitation", back_populates="source")


class LegalInstitution(Base):
    __tablename__ = "legal_institutions"

    inst_id = Column(Integer, primary_key=True, index=True)
    osm_id = Column(Text, unique=True, nullable=True)
    name = Column(Text, nullable=True)
    amenity = Column(Text, nullable=True)
    office = Column(Text, nullable=True)
    type = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    jurisdiction = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    template_id = Column(Integer, primary_key=True, index=True)
    type = Column(Text, nullable=False)
    language = Column(Text, nullable=False, default="en")
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    fields_schema = Column(Text, nullable=True)
    sample_content = Column(Text, nullable=True)

    documents = relationship("Document", back_populates="template")


class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    template_id = Column(Integer, ForeignKey("document_templates.template_id"), nullable=True)
    title = Column(Text, nullable=False)
    type = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    input_data = Column(Text, nullable=True)
    pdf_data = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="documents")
    template = relationship("DocumentTemplate", back_populates="documents")
    analysis = relationship("DocAnalysis", back_populates="document", uselist=False)


class DocAnalysis(Base):
    __tablename__ = "doc_analysis"

    analysis_id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    file_name = Column(Text, nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(Text, nullable=False, default="pending")
    summary = Column(Text, nullable=True)
    risks = Column(Text, nullable=True)
    key_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="analysis")


class Complaint(Base):
    __tablename__ = "complaints"

    complaint_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    content = Column(Text, nullable=False)

    user = relationship("User", back_populates="complaints")


class QAInteraction(Base):
    __tablename__ = "qa_interactions"

    qa_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    language = Column(Text, nullable=False, default="en")
    status = Column(Text, nullable=False, default="pending")
    session_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="qa_interactions")
    citations = relationship("QACitation", back_populates="qa")


class QACitation(Base):
    __tablename__ = "qa_citations"

    citation_id = Column(Integer, primary_key=True, index=True)
    qa_id = Column(Integer, ForeignKey("qa_interactions.qa_id"), nullable=False)
    source_id = Column(Integer, ForeignKey("legal_sources.source_id"), nullable=True)
    snippet_text = Column(Text, nullable=True)
    source_title = Column(Text, nullable=True)
    citation_ref = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    qa = relationship("QAInteraction", back_populates="citations")
    source = relationship("LegalSource", back_populates="qa_citations")


class RatingReview(Base):
    __tablename__ = "rating_reviews"

    rating_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    lawyer_id = Column(Integer, ForeignKey("lawyer_profiles.lawyer_id"), nullable=False)
    stars = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "lawyer_id", name="uq_user_lawyer_review"),
    )

    user = relationship("User", back_populates="ratings_given")
    lawyer_profile = relationship("LawyerProfile", back_populates="reviews", foreign_keys=[lawyer_id])


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    law_domain = Column(Text, nullable=False)
    jurisdiction = Column(Text, nullable=True)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="cases")
    assignments = relationship("CaseAssignment", back_populates="case")
    requests = relationship("Request", back_populates="case")
    messages = relationship("CaseMessage", back_populates="case")


class Request(Base):
    __tablename__ = "requests"

    request_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.case_id"), nullable=False)
    lawyer_id = Column(Integer, ForeignKey("lawyer_profiles.lawyer_id"), nullable=False)
    status = Column(Text, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    case = relationship("Case", back_populates="requests")
    user = relationship("User", back_populates="requests")
    lawyer_profile = relationship("LawyerProfile", back_populates="requests")


class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    assignment_id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.case_id"), nullable=False)
    lawyer_id = Column(Integer, ForeignKey("lawyer_profiles.lawyer_id"), nullable=False)
    status = Column(Text, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    case = relationship("Case", back_populates="assignments")
    lawyer_profile = relationship("LawyerProfile", back_populates="assignments")


class Appointment(Base):
    __tablename__ = "appointments"

    appt_id = Column(Integer, primary_key=True, index=True)
    mode_of_comm = Column(Text, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Text, nullable=False, default="pending")  # pending, accepted, rejected, cancelled
    notes = Column(Text, nullable=True)
    meeting_link = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    lawyer_id = Column(Integer, ForeignKey("lawyer_profiles.lawyer_id"), nullable=False)

    user = relationship("User", back_populates="appointments")
    lawyer = relationship("LawyerProfile", back_populates="appointments")


class CaseMessage(Base):
    __tablename__ = "case_messages"

    message_id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.case_id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    case = relationship("Case", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id])



class Conversation(Base):
    __tablename__ = "conversations"

    conv_id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    participants = relationship("ConversationParticipant", back_populates="conversation", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    id = Column(Integer, primary_key=True, index=True)
    conv_id = Column(Integer, ForeignKey("conversations.conv_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("conv_id", "user_id", name="uq_conv_participant"),
        Index("ix_conv_participant_user_id", "user_id"),
    )

    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User", back_populates="conversation_participants")


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, index=True)
    conv_id = Column(Integer, ForeignKey("conversations.conv_id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("length(trim(content)) > 0", name="ck_message_content_not_blank"),
        Index("ix_message_conv_created", "conv_id", "created_at"),
    )

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
