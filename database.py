import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Ładujemy zmienne z pliku .env
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+mysqlconnector://root:@localhost:3306/domowy_budzet"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: SessionLocal = Depends(get_db)
):
    # Import tutaj żeby uniknąć circular import
    import models

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
    user = db.query(models.User).filter(
        models.User.username == username
    ).first()
    if user is None:
        raise credentials_exception
    return user


def get_data_owner_id(
    current_user,
    db: SessionLocal
) -> int:
    """
    Zwraca owner_id dla zapytań do bazy:
    - Admin → widzi swoje dane (current_user.id)
    - Viewer → widzi dane admina który go zaprosił (owner_id z user_data_access)
    """
    # Import tutaj żeby uniknąć circular import
    import models

    if current_user.role == "admin":
        return current_user.id

    # Viewer — znajdź właściciela danych
    access = db.query(models.UserDataAccess).filter(
        models.UserDataAccess.user_id == current_user.id
    ).first()

    if not access:
        raise HTTPException(
            status_code=403,
            detail="Brak dostępu do danych"
        )

    return access.owner_id
