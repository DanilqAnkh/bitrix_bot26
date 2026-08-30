from sqlalchemy.orm import Session
from app.database.models import User, Message


def get_user(db: Session, telegram_id: int,) -> User: #creating if user not exist 
    user = (db.query(User).filter(User.telegram_id == telegram_id).first())

    if user:
        return user

    user = User(telegram_id = telegram_id)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def create_message(db: Session, user_id: int, role: str, text: str) -> Message:
    message = Message(user_id=user_id, role=role, text=text)
    db.add(message)
    db.commit()
    db.refresh(message)

    return message 
