"""Journal des actions administratives (cahier §16.5 et §19)."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(db: Session, actor_id: int | None, action: str, entity_type: str, entity_id: int | None, **details) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))
