import logging
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.db import engine, Base, get_db, SessionLocal
from backend.app.api import cases, batch, metrics, auth
from backend.app.pipeline.detection import verify_razorpay_signature, process_webhook_payload

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("retry_backend")

app = FastAPI(
    title="Retry Revenue Recovery Agent API",
    description="Backend API for the Razorpay AI Buildathon Revenue Recovery Agent",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    # Log and print the database path on FastAPI startup
    import os
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        if db_url.startswith("sqlite:///"):
            db_path = db_url[10:]
        else:
            db_path = db_url[9:]
        abs_path = os.path.abspath(db_path)
        logger.info(f"FastAPI Startup: SQLite absolute path is: {abs_path}")
        print(f"FASTAPI STARTUP: SQLite database absolute path is: {abs_path}")
    else:
        logger.info(f"FastAPI Startup: Database URL is: {db_url}")
        print(f"FASTAPI STARTUP: Database URL is: {db_url}")
        
    # Guarantee tables are created at startup
    Base.metadata.create_all(bind=engine)
    logger.info("FastAPI Startup: Database tables checked/created successfully.")

    # Initialize default demo user account if not present
    db = SessionLocal()
    try:
        auth.ensure_demo_user(db)
        logger.info("FastAPI Startup: Demo account (demo@razorpay.com) ensured.")
    finally:
        db.close()

# CORS Configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # NextJS development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(cases.router, prefix="/api/v1")
app.include_router(batch.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "Retry Revenue Recovery Agent API",
        "database": settings.DATABASE_URL.split(":")[0]  # Show driver name
    }

@app.post("/api/v1/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
    bypass_signature: bool = False,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint to receive failed and captured payment triggers from Razorpay.
    For production, signature verification is strictly enforced.
    For local buildathon demos, signature verification can be bypassed if bypass_signature=True.
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    
    # Parse payload
    try:
        payload = json_data = request.scope.get("_json_data") # handle potential pre-parsed body
        if not payload:
            import json
            payload = json.loads(body_str)
    except Exception as e:
        logger.error("Failed to parse webhook JSON body: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Enforce signature verification unless explicitly bypassed for sandbox simulations
    if not bypass_signature and settings.RAZORPAY_WEBHOOK_SECRET != "dummy_webhook_secret":
        if not x_razorpay_signature:
            logger.warning("Rejected webhook: missing Razorpay signature header.")
            raise HTTPException(status_code=400, detail="Missing signature header")
            
        verified = verify_razorpay_signature(body_bytes, x_razorpay_signature, settings.RAZORPAY_WEBHOOK_SECRET)
        if not verified:
            logger.warning("Rejected webhook: invalid signature. Check webhook secret.")
            raise HTTPException(status_code=401, detail="Invalid signature")

    logger.info("Received Razorpay Webhook Event: %s", payload.get("event"))

    try:
        case = process_webhook_payload(db, payload)
        if case:
            return {"status": "processed", "case_id": case.id, "leak_type": case.leak_type, "status": case.status}
        else:
            return {"status": "ignored", "reason": "No active case matches event"}
    except Exception as e:
        logger.error("Error processing webhook payload: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal processing error: {str(e)}")
