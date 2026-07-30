import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.test_runs import router as test_runs_router
from app.core.ws_manager import ws_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title=settings.app_name)

# Include API Routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(test_runs_router)

# Enable CORS for React/Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

