from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import uuid
from datetime import datetime
from sqlalchemy.dialects.sqlite import insert

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

# ------------------- Models -------------------

class ExtractionStatus(Base):
    __tablename__ = 'extraction_status'
    id = Column(String, primary_key=True, default=generate_uuid)
    connection_id = Column(String, primary_key=True)
    status = Column(String)  # e.g. in_progress, completed, failed
    config = Column(JSON, nullable=False)  # full config payload as JSON
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # relationship to calendar events
    events = relationship("CalendarEvent", back_populates="extraction", cascade="all, delete-orphan")

    # relationship to next_links (one-to-many)
    next_links = relationship("ExtractionNextLink", back_populates="extraction", cascade="all, delete-orphan")


class ExtractionNextLink(Base):
    __tablename__ = "extraction_next_links"

    id = Column(String, primary_key=True, default=generate_uuid)
    connection_id = Column(String, ForeignKey("extraction_status.connection_id"), nullable=False)
    user_upn = Column(String, nullable=False)  # the user principal name
    next_link = Column(Text, nullable=True)  # next page URL for that user, nullable if no next link

    extraction = relationship("ExtractionStatus", back_populates="next_links")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # ← ADD THIS LINE

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    connection_id = Column(String, ForeignKey("extraction_status.connection_id"), nullable=False)
    event_id = Column(String, nullable=False, unique=True)  # Add unique=True
    tenant_id = Column(String, nullable=False)
    organizer_name = Column(String)
    organizer_email = Column(String)
    title = Column(String)
    description = Column(Text)
    location = Column(String)
    virtual = Column(Boolean, default=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    organizer_response = Column(String)
    allow_new_time_proposals = Column(Boolean, default=False)
    attendees = Column(JSON)
    date_extracted = Column(DateTime, default=datetime.utcnow)

    extraction = relationship("ExtractionStatus", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "connection_id": self.connection_id,
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "organizer_name": self.organizer_name,
            "organizer_email": self.organizer_email,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "virtual": self.virtual,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "organizer_response": self.organizer_response,
            "allow_new_time_proposals": self.allow_new_time_proposals,
            "attendees": self.attendees,
            "date_extracted": self.date_extracted.isoformat() if self.date_extracted else None
        }


# ------------------- DB Setup -------------------

engine = create_engine("sqlite:///calendar_data.db")  # Change to PostgreSQL/MySQL URL as needed
Session = sessionmaker(bind=engine)
session = Session()


def init_db():
    Base.metadata.create_all(engine)


# ------------------- Status Functions -------------------

def get_extraction(connection_id: str):
    return session.query(ExtractionStatus).filter_by(connection_id=connection_id).first()


def save_extraction(connection_id, status, config=None, result=None, error=None, started_at=None, completed_at=None):
    extraction = get_extraction(connection_id)
    if extraction:
        extraction.status = status
        extraction.error = error
        extraction.completed_at = completed_at or datetime.utcnow()
        # Is config updated here? If not, that’s okay for updates.
    else:
        extraction = ExtractionStatus(
            connection_id=connection_id,
            status=status,
            config=config,
            error=error,
            started_at=started_at or datetime.utcnow(),
            completed_at=completed_at
        )
        session.add(extraction)

    session.commit()
    return extraction


# ------------------- Calendar Event Functions -------------------

def save_calendar_events(connection_id, events: list):
    extraction = get_extraction(connection_id)
    if not extraction:
        raise Exception("ExtractionStatus must exist before saving events.")

    for event in events:
        stmt = insert(CalendarEvent).values(
            connection_id=connection_id,
            event_id=event["event_id"],
            tenant_id=event["tenant_id"],
            organizer_name=event.get("organizer_name"),
            organizer_email=event.get("organizer_email"),
            title=event.get("title"),
            description=event.get("description"),
            location=event.get("location"),
            virtual=event.get("virtual", False),
            start_time=event.get("start_time"),
            end_time=event.get("end_time"),
            organizer_response=event.get("organizer_response"),
            allow_new_time_proposals=event.get("allow_new_time_proposals", False),
            attendees=event.get("attendees"),
            date_extracted=event.get("date_extracted")
        ).on_conflict_do_nothing(
            index_elements=['event_id']  # your unique constraint column(s)
        )

        session.execute(stmt)

    session.commit()


def get_events_by_connection_id(connection_id: str):
    extraction = get_extraction(connection_id)
    if not extraction:
        return []
    print(connection_id)
    return session.query(CalendarEvent).filter_by(connection_id=connection_id).all()


# ------------------- Utility -------------------

def parse_dt(dt_str):
    try:
        return datetime.datetime.fromisoformat(dt_str)
    except Exception:
        return None  # or raise, depending on strictness


def get_next_link(connection_id, user_upn):
    # Query your DB table ExtractionNextLink for next_link
    record = session.query(ExtractionNextLink).filter_by(
        connection_id=connection_id, user_upn=user_upn
    ).first()
    return record.next_link if record else None

def save_next_link(connection_id, user_upn, next_link):
    # Insert or update ExtractionNextLink record
    record = session.query(ExtractionNextLink).filter_by(
        connection_id=connection_id, user_upn=user_upn
    ).first()
    if record:
        record.next_link = next_link
        record.updated_at = datetime.utcnow()
    else:
        record = ExtractionNextLink(
            connection_id=connection_id,
            user_upn=user_upn,
            next_link=next_link,
            updated_at=datetime.utcnow()
        )
        session.add(record)
    session.commit()

def clear_all_next_links(connection_id):
    # Delete all next links for this connection_id
    session.query(ExtractionNextLink).filter_by(
        connection_id=connection_id
    ).delete()
    session.commit()

