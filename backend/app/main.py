from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import endpoints
from app.db.session import Base, engine
from app.config import ALLOWED_ORIGINS, ENV, DEBUG

app = FastAPI(title="Study Abroad Intake Chatbot")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    return response

@app.get("/health")
def health():
    return {"status": "ok", "env": ENV}

@app.get("/ready")
def ready():
    # In future, check downstream dependencies
    return {"status": "ready"}

app.include_router(endpoints.router, prefix="/api")
try:
    from pathlib import Path
    frontend_build_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_build_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_build_dir), html=True), name="frontend")
except Exception:
    pass


@app.on_event("startup")
def on_startup_create_tables():
    # Only auto-create tables in development
    if ENV == "development" or DEBUG:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass


@app.get("/")
def root():
    return RedirectResponse(url="/docs")
