from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from backend.app.db import get_db
from backend.app.pipeline.detection import seed_demo_cases
from backend.app.pipeline.scheduler import sweep_scheduled_actions, check_and_reactivate_promises

router = APIRouter(prefix="/batch", tags=["Batch Simulations"])

class SeedRequest(BaseModel):
    num_cases: int = 10

class RunRequest(BaseModel):
    simulated_time: Optional[str] = None  # ISO format: YYYY-MM-DDTHH:MM:SS

@router.post("/seed")
def seed_database(req: SeedRequest = Body(...), db: Session = Depends(get_db)):
    if req.num_cases < 1 or req.num_cases > 100:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 100")
        
    try:
        cases = seed_demo_cases(db, req.num_cases)
        return {
            "message": f"Successfully seeded {len(cases)} cases with full recovery pipelines.",
            "seeded_count": len(cases)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to seed database: {str(e)}")


@router.post("/run")
def trigger_simulation_sweep(req: RunRequest = Body(...), db: Session = Depends(get_db)):
    """
    Simulates a scheduler execution tick.
    Optionally accepts a 'simulated_time' parameter to run time-of-day or overdue promise logic.
    """
    now = datetime.utcnow()
    if req.simulated_time:
        try:
            now = datetime.fromisoformat(req.simulated_time.replace("Z", ""))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid simulated_time format. Must be ISO-8601.")

    try:
        # 1. Sweep pending actions
        actions_run = sweep_scheduled_actions(db, now)
        
        # 2. Check overdue promises
        promises_reactivated = check_and_reactivate_promises(db, now)
        
        return {
            "message": "Simulation tick executed successfully.",
            "simulated_time": now.isoformat(),
            "actions_executed": actions_run,
            "promises_reactivated": promises_reactivated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation sweep failed: {str(e)}")


from fastapi import BackgroundTasks

@router.post("/evaluate")
def trigger_evaluation(background_tasks: BackgroundTasks):
    from backend.eval.run_eval import run_evaluation
    background_tasks.add_task(run_evaluation)
    return {
        "status": "started",
        "message": "Offline diagnostics evaluation started in the background."
    }
