from sqlalchemy import Column, Integer, String, Text
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    uuid = Column(String(36), unique=True, nullable=False)
    email_tag = Column(String(128), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(Integer, nullable=False)
    expiry_at = Column(Integer, nullable=True)
    data_cap_bytes = Column(Integer, nullable=True)
    bytes_used = Column(Integer, nullable=False, default=0)
    max_devices = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    vless_uri = Column(Text, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    ts = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)
    username = Column(String(64), nullable=False)
    actor = Column(String(64), nullable=False, default="admin")
    detail = Column(Text, nullable=True)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)