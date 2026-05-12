"""
models.py — ORM table definitions
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text
from database import Base


class Conversion(Base):
    """One record per conversion job."""
    __tablename__ = "conversions"

    id                = Column(String(36),  primary_key=True, index=True)   # UUID
    original_filename = Column(String(255), nullable=False)
    output_filename   = Column(String(255), nullable=False)

    # Sizes in bytes
    file_size_in      = Column(BigInteger, default=0)
    file_size_out     = Column(BigInteger, default=0)

    # Lifecycle
    status            = Column(String(20),  default="queued")   # queued | processing | done | error
    created_at        = Column(DateTime,    default=datetime.utcnow)
    completed_at      = Column(DateTime,    nullable=True)

    # Paths & errors
    output_path       = Column(Text,        nullable=True)
    error_message     = Column(Text,        nullable=True)

    def __repr__(self):
        return f"<Conversion id={self.id} file={self.original_filename} status={self.status}>"