"""
Credence Core — Base Repository
Provides common transactional session management.
"""

from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session
from backend.app.core.database import get_db

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class

    def get_by_id(self, db: Session, entity_id: int) -> Optional[T]:
        return db.query(self.model_class).filter(getattr(self.model_class, "id") == entity_id).first()

    def list_all(self, db: Session) -> List[T]:
        return db.query(self.model_class).all()

    def add(self, db: Session, entity: T) -> T:
        db.add(entity)
        db.flush()
        return entity

    def delete(self, db: Session, entity: T):
        db.delete(entity)
        db.flush()
