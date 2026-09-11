"""YugKrit - Notification service."""

import json

from database.database import db
from database.models import Notification


def notify(user, title, message, link=None, notification_type="SYSTEM", entity_type=None, entity_id=None, metadata=None):
    if not user:
        return None
    payload = {"link": link, "notification_type": notification_type, "entity_type": entity_type, "entity_id": entity_id}
    if metadata is not None:
        payload.update(metadata)
    note = Notification(
        user_id=user.id,
        title=title,
        message=message,
        link=link,
        notification_type=notification_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=json.dumps(metadata) if metadata is not None else None,
    )
    db.session.add(note)
    db.session.commit()
    return note


def notify_many(users, title, message, link=None, notification_type="SYSTEM", entity_type=None, entity_id=None, metadata=None):
    created = []
    for u in users:
        created.append(notify(u, title, message, link, notification_type, entity_type, entity_id, metadata))
    return created


def get_for_user(user, limit=20):
    if not user:
        return []
    return Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(limit).all()


def unread_count(user):
    if not user:
        return 0
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def mark_read(user, notification_id):
    note = Notification.query.filter_by(id=notification_id, user_id=user.id).first()
    if note:
        note.is_read = True
        db.session.commit()
    return note


def mark_all_read(user):
    if not user:
        return 0
    updated = Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return updated

