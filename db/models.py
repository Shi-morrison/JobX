from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    ForeignKey, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    description = Column(Text)
    source = Column(String)           # linkedin / indeed / glassdoor
    posted_date = Column(DateTime)
    fit_score = Column(Float)         # 1–10, set by scorer agent
    ats_score = Column(Float)         # 0–100%, set by scorer agent
    gap_analysis = Column(JSON)       # {hard_gaps, soft_gaps, reframe_suggestions}
    status = Column(String, default="new")  # new / scored / applied / interviewing / rejected / offer
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("Application", back_populates="job")
    contacts = relationship("Contact", back_populates="job")
    resume_versions = relationship("ResumeVersion", back_populates="job")
    interview_prep = relationship("InterviewPrep", back_populates="job", uselist=False)
    interview_outcome = relationship("InterviewOutcome", back_populates="job", uselist=False)


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    applied_date = Column(DateTime, default=datetime.utcnow)
    resume_version_path = Column(String)
    cover_letter_path = Column(String)
    status = Column(String, default="submitted")  # submitted / acknowledged / interviewing / rejected / offer
    notes = Column(Text)

    job = relationship("Job", back_populates="applications")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    name = Column(String)
    title = Column(String)
    linkedin_url = Column(String)
    email = Column(String)
    company = Column(String)

    job = relationship("Job", back_populates="contacts")
    outreach_sequences = relationship("OutreachSequence", back_populates="contact")


class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)
    message_type = Column(String)     # linkedin / email
    content = Column(Text)            # generated message text
    sent_at = Column(DateTime)
    follow_up_due = Column(DateTime)
    response_received = Column(Boolean, default=False)
    status = Column(String, default="pending")  # pending / sent / followed_up / ghosted / responded

    contact = relationship("Contact", back_populates="outreach_sequences")


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    file_path = Column(String, nullable=False)
    changes_summary = Column(Text)
    ats_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="resume_versions")


class CompanyResearch(Base):
    __tablename__ = "company_research"

    id = Column(Integer, primary_key=True)
    company_name = Column(String, unique=True, nullable=False)
    glassdoor_rating = Column(Float)
    funding_stage = Column(String)
    employee_count = Column(String)   # e.g. "1,000–5,000"
    industry = Column(String)
    recent_news = Column(JSON)        # list of {title, url, snippet}
    tech_stack = Column(JSON)         # list of technology names
    layoff_history = Column(JSON)     # list of {headline, url, date}
    summary = Column(Text)            # Claude-synthesized 2–3 sentence overview
    created_at = Column(DateTime, default=datetime.utcnow)


class SalaryData(Base):
    __tablename__ = "salary_data"

    id = Column(Integer, primary_key=True)
    company_name = Column(String, nullable=False)
    role_level = Column(String)       # junior / mid / senior / staff
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    equity = Column(String)
    source = Column(String)           # levels.fyi / glassdoor
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewPrep(Base):
    __tablename__ = "interview_prep"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    technical_questions = Column(JSON)   # {technology: [q1, q2, ...]}
    behavioral_questions = Column(JSON)  # [{question, star_framework}]
    company_questions = Column(JSON)     # [{question, talking_point}]
    study_plan = Column(JSON)            # [{topic, resources, hours}]
    mock_sessions = Column(JSON)         # [{timestamp, qa_pairs: [{q, answer, score, critique}]}]
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="interview_prep")


class InterviewOutcome(Base):
    __tablename__ = "interview_outcomes"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    stage_reached = Column(String)    # phone_screen / technical / onsite / final / offer
    rejection_reason = Column(Text)
    feedback = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="interview_outcome")
