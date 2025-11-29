"""
ANPR FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from application.helpers.logger import get_logger
from application.database.base import Base
from application.database.database import engine
import application.database

# Import routers
from application.auth.routes import router as auth_router
from application.edge.routes import router as edge_router
from application.checkpoint.routes import router as checkpoint_router
from application.dashboard.routes import router as dashboard_router
from application.watchlist.routes import router as watchlist_router
from application.notification.routes import router as notification_router
from application.configuration.routes import router as configuration_router

logger = get_logger("main")

app = FastAPI(title="ANPR APIs", version="1.0")

# CORS Configuration - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Include routers
app.include_router(auth_router)
app.include_router(edge_router)
app.include_router(checkpoint_router)
app.include_router(dashboard_router)
app.include_router(watchlist_router)
app.include_router(notification_router)
app.include_router(configuration_router)

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    logger.info("ANPR Initialized :: Database -> Connected :: Endpoints -> Available")

@app.get("/")
def read_root():
    """
    Root endpoint.
    Returns a welcome message indicating that the ANPR API service is running.
    """
    return {"message": "Welcome to my FastAPI- ANPR app!"}