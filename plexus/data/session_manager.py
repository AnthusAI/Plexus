from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
import logging

class SessionManager:
    def __init__(self, engine):
        self.engine = engine
        self.Session = scoped_session(sessionmaker(bind=engine))
        self._current_session = None

    @contextmanager
    def get_session(self):
        """Get a database session with automatic renewal on errors."""
        session = None
        try:
            session = self.Session()
            self._current_session = session
            # Ensure the session is bound to the engine
            session.bind = self.engine
            yield session
            session.commit()
        except SQLAlchemyError as e:
            if session:
                session.rollback()
            logging.error(f"Database error: {str(e)}")
            # Try to renew the session
            if self._current_session:
                self._current_session.close()
                self._current_session = None
            raise
        finally:
            if session:
                session.close()
                if session == self._current_session:
                    self._current_session = None
                # Remove the session from the scoped session registry
                self.Session.remove()

    def renew_session(self):
        """Force renewal of the current session."""
        if self._current_session:
            self._current_session.close()
            self._current_session = None
        # Remove any existing sessions from the registry
        self.Session.remove()
        return self.get_session() 