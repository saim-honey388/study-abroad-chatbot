from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import endpoints
from app.db.session import Base, engine
from app.config import ALLOWED_ORIGINS, ENV, DEBUG
import time
import logging
import os
from dotenv import load_dotenv
from openai import OpenAI

# -----------------
# Load env + client
# -----------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Study Abroad Intake Chatbot")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request latency middleware
_req_logger = logging.getLogger("request_timing")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Record when request arrives at backend
    backend_received_time = time.perf_counter()
    request_start_time = time.time()  # Unix timestamp for frontend reference
    
    # Extract client timestamp if available
    client_timestamp = request.headers.get("x-client-timestamp")
    if client_timestamp:
        try:
            client_time = float(client_timestamp)
            network_latency_ms = (backend_received_time * 1000) - (client_time * 1000)
            print(f"🌐 Network latency (client->backend): {network_latency_ms:.1f}ms")
        except (ValueError, TypeError):
            pass
    
    # Process request
    start = time.perf_counter()
    response = await call_next(request)
    processing_time_ms = (time.perf_counter() - start) * 1000.0
    total_time_ms = (time.perf_counter() - backend_received_time) * 1000.0
    
    # Log comprehensive timing
    print(f"⏱️  API Request Timing:")
    print(f"   📥 Backend received: {backend_received_time:.3f}s")
    print(f"   ⚙️  Processing time: {processing_time_ms:.1f}ms")
    print(f"   📤 Total backend time: {total_time_ms:.1f}ms")
    print(f"   🔄 {request.method} {request.url.path} -> {response.status_code}")
    
    # Add timing headers for frontend
    response.headers["x-backend-processing-time-ms"] = str(int(processing_time_ms))
    response.headers["x-total-backend-time-ms"] = str(int(total_time_ms))
    response.headers["x-backend-timestamp"] = str(time.time())
    
    return response

@app.get("/health")
def health():
    return {"status": "ok", "env": ENV}

@app.get("/ready")
def ready():
    return {"status": "ready"}

# -----------------
# OpenAI test route
# -----------------
@app.get("/openai/chat")
async def openai_chat(prompt: str):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}

# -----------------
# API + frontend
# -----------------
app.include_router(endpoints.router, prefix="/api")
try:
    from pathlib import Path
    frontend_build_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend_build_dir.exists():
        app.mount(
            "/", StaticFiles(directory=str(frontend_build_dir), html=True), name="frontend"
        )
except Exception:
    pass

@app.on_event("startup")
def on_startup_create_tables():
    if ENV == "development" or DEBUG:
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

@app.get("/")
def root():
    return RedirectResponse(url="/docs")
