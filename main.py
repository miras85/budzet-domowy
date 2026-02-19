from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import models, database, auth
from routers import auth as auth_router
from routers import finance as finance_router
from routers import recurring as recurring_router
from collections import defaultdict
from datetime import datetime, timedelta

# Prosta implementacja rate limiting
login_attempts = defaultdict(list)

def check_rate_limit(ip: str, limit: int = 5, window: int = 60) -> bool:
    """Sprawdza czy IP przekroczył limit prób w danym oknie czasowym"""
    now = datetime.now()
    cutoff = now - timedelta(seconds=window)
    
    # Usuń stare próby
    login_attempts[ip] = [t for t in login_attempts[ip] if t > cutoff]
    
    # Sprawdź limit
    if len(login_attempts[ip]) >= limit:
        return False
    
    # Dodaj nową próbę
    login_attempts[ip].append(now)
    return True

# Inicjalizacja bazy
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/token" and request.method == "POST":
        client_ip = request.client.host
        
        if not check_rate_limit(client_ip, limit=5, window=60):
            print(f"🚫 BLOCKED IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Zbyt wiele prób logowania. Spróbuj za 1 minutę."}
            )
    
    response = await call_next(request)
    return response
# Dołączamy routery
app.include_router(auth_router.router)
app.include_router(finance_router.router)
app.include_router(recurring_router.router)

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

@app.get("/sw.js")
async def service_worker():
    return FileResponse('static/sw.js', media_type='application/javascript')
