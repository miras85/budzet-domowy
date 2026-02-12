from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import models, database, auth
from routers import auth as auth_router
from routers import finance as finance_router

# Inicjalizacja bazy
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Dołączamy routery
app.include_router(auth_router.router)
app.include_router(finance_router.router)

print("--- SYSTEM STARTUP: WERSJA MODULARNA ---")

# Tworzenie admina przy starcie
@app.on_event("startup")
def create_default_user():
    db = database.SessionLocal()
    user = db.query(models.User).filter(models.User.username == "admin").first()
    if not user:
        print("--- TWORZENIE UŻYTKOWNIKA ADMIN ---")
        hashed_pwd = auth.get_password_hash("admin")
        new_user = models.User(username="admin", hashed_password=hashed_pwd)
        db.add(new_user)
        db.commit()
    db.close()

# Pliki statyczne (Frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')
