from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
import secrets
import database, models, auth, schemas

router = APIRouter(tags=["Authentication"])

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Błędny login lub hasło",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }

@router.get("/api/users/me")
def get_current_user_info(
    current_user: models.User = Depends(database.get_current_user)
):
    """Zwraca info o zalogowanym userze"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    }

@router.post("/api/invite")
def create_invitation(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Admin generuje jednorazowy link zaproszenia"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Tylko admin może zapraszać użytkowników"
        )

    # Unieważnij stare niewykorzystane zaproszenia tego admina
    db.query(models.Invitation).filter(
        models.Invitation.created_by == current_user.id,
        models.Invitation.used == False
    ).delete()

    # Stwórz nowe zaproszenie
    token = secrets.token_urlsafe(32)
    invitation = models.Invitation(
        token=token,
        created_by=current_user.id,
        used=False,
        expires_at=datetime.utcnow() + timedelta(hours=48)
    )
    db.add(invitation)
    db.commit()

    return {
        "token": token,
        "expires_at": str(invitation.expires_at),
        "invite_url": f"/register?token={token}"
    }

@router.post("/api/register")
def register_with_invite(
    user: schemas.UserCreate,
    token: str,
    db: Session = Depends(database.get_db)
):
    """Rejestracja nowego usera przez token zaproszenia"""

    # Sprawdź token
    invitation = db.query(models.Invitation).filter(
        models.Invitation.token == token,
        models.Invitation.used == False,
        models.Invitation.expires_at > datetime.utcnow()
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=400,
            detail="Token zaproszenia jest nieprawidłowy lub wygasł"
        )

    # Sprawdź czy username wolny
    if db.query(models.User).filter(
        models.User.username == user.username
    ).first():
        raise HTTPException(
            status_code=400,
            detail="Taki użytkownik już istnieje"
        )

    # Stwórz usera z rolą viewer
    hashed_pwd = auth.get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        hashed_password=hashed_pwd,
        role="viewer",
        invited_by=invitation.created_by
    )
    db.add(new_user)
    db.flush()

    # Daj dostęp do danych admina
    access = models.UserDataAccess(
        user_id=new_user.id,
        owner_id=invitation.created_by
    )
    db.add(access)

    # Oznacz token jako użyty
    invitation.used = True

    db.commit()

    return {
        "status": "registered",
        "username": new_user.username,
        "role": new_user.role
    }

@router.post("/api/users")
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    """Tworzenie usera przez admina (stary endpoint)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    if db.query(models.User).filter(
        models.User.username == user.username
    ).first():
        raise HTTPException(
            status_code=400,
            detail="Taki użytkownik już istnieje"
        )
    hashed_pwd = auth.get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        hashed_password=hashed_pwd,
        role="admin"
    )
    db.add(new_user)
    db.commit()
    return {"status": "created", "user": user.username}

@router.post("/api/users/change-password")
def change_password(
    pwd: schemas.PasswordChange,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(database.get_current_user)
):
    if not auth.verify_password(pwd.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Stare hasło jest nieprawidłowe"
        )
    current_user.hashed_password = auth.get_password_hash(pwd.new_password)
    db.commit()
    return {"status": "password_changed"}
