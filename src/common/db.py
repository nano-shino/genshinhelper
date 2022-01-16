from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session

engine = create_engine("sqlite:///genshinhelper.db", future=True)
session_factory = sessionmaker(bind=engine)
session: Session = scoped_session(session_factory)()
