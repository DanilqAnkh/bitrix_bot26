from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, Session
from datetime import datetime
from typing import Optional, List 


Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key = True)
    telegram_id = Column(BigInteger, unique = True, nullable = False, index = True)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates = "user")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key = True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable = False)
    role = Column(String, nullable = False)
    text = Column(String, nullable = False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates = "messages")    