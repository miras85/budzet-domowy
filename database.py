import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Ładujemy zmienne z pliku .env
load_dotenv()

# Pobieramy adres z pliku .env (lub używamy domyślnego, jeśli brak pliku)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://root:@localhost:3306/domowy_budzet")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,        # Sprawdza czy połączenie żyje przed użyciem
    pool_recycle=3600,         # Odświeża połączenia co 1h (przed MySQL timeout)
    pool_size=5,               # Max 5 połączeń w puli
    max_overflow=10            # Max 10 dodatkowych połączeń
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import auth
import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: SessionLocal = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowe dane logowania",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except auth.JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user
