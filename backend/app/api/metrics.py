from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.pipeline.metrics import calculate_metrics

router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.get("")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    metrics = calculate_metrics(db)
    return metrics
