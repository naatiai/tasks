from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Mocks(Base):
    __tablename__ = "mocks"

    # id = Column(String, primary_key=True, default=lambda: nanoid.generate(size=7))
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    time_duration = Column(Integer, nullable=False)
    no_of_qa = Column(Integer, nullable=False)
    language = Column(String, default="Hindi")
    created_on = Column(DateTime, default=datetime.utcnow)

    mock_questions = relationship("MockQuestions", back_populates="mock")
    mock_answers = relationship("MockAnswers", back_populates="mock")
    user_mocks = relationship("UserMocks", back_populates="mock")


class MockQuestions(Base):
    __tablename__ = "mock_questions"

    # id = Column(String, primary_key=True, default=lambda: nanoid.generate(size=7))
    id = Column(String, primary_key=True)
    mock_id = Column(String, ForeignKey("mocks.id"), nullable=False)
    audio_file_url = Column(Text, nullable=False)
    order = Column(Integer, default=1)
    transcript = Column(Text, nullable=False)
    language = Column(String, default="English")
    answer_language = Column(String, default="English")
    created_on = Column(DateTime, default=datetime.utcnow)

    mock = relationship("Mocks", back_populates="mock_questions")
    mock_answers = relationship("MockAnswers", back_populates="mock_question")


class MockAnswers(Base):
    __tablename__ = "mock_answers"

    # id = Column(String, primary_key=True, default=lambda: nanoid.generate(size=7))
    id = Column(String, primary_key=True)
    mock_question_id = Column(String, ForeignKey(
        "mock_questions.id"), nullable=False)
    user_mock_id = Column(String, ForeignKey("user_mocks.id"), nullable=False)
    user_id = Column(String, nullable=False)
    audio_file_url = Column(Text, nullable=False)
    transcript = Column(Text)
    score = Column(Integer)
    max_score = Column(Integer, default=5)
    is_correct = Column(Boolean)
    expires_on = Column(DateTime)
    created_on = Column(DateTime, default=datetime.utcnow)
    mock_id = Column(String, ForeignKey("mocks.id"))

    mock_question = relationship(
        "MockQuestions", back_populates="mock_answers")
    mock = relationship("Mocks", back_populates="mock_answers")
    user_mock = relationship("UserMocks", back_populates="mock_answers")


class UserMocks(Base):
    __tablename__ = "user_mocks"

    id = Column(String, primary_key=True)
    mock_id = Column(String, ForeignKey("mocks.id"),
                     nullable=False)  # Foreign key to Mocks table
    user_id = Column(String, nullable=False)  # User ID
    attempts_allowed = Column(Integer, default=1)  # Default attempts allowed
    attempts = Column(Integer, default=0)  # Number of attempts made
    total_score = Column(Integer, nullable=True)  # Nullable total score
    passed = Column(Boolean, nullable=True)  # Nullable passed status
    expired = Column(Boolean, default=False)  # Default expired status
    # Timestamp with default to current time
    created_on = Column(DateTime, default=datetime.utcnow)

    # Relationships
    # One-to-many relationship with Mocks
    mock = relationship("Mocks", back_populates="user_mocks")
    # One-to-many relationship with MockAnswers
    mock_answers = relationship("MockAnswers", back_populates="user_mock")
