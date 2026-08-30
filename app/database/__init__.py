from app.database.db import engine
from app.database.models import Base


def init_db():
    Base.metadata.create_all(bind=engine)