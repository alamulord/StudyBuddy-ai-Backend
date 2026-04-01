from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from typing import Any, Optional, Annotated
from supabase import Client

from app.core.config import settings
from app.core.deps import get_supabase
from app.services.processing import process_material

router = APIRouter()


def require_admin_api_key(
    x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-Api-Key"),
):
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if x_admin_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.get("/ai-runs")
def list_ai_runs(
    _: Annotated[bool, Depends(require_admin_api_key)],
    supabase: Client = Depends(get_supabase),
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    material_id: Optional[str] = None,
    limit: int = 100,
) -> Any:
    query = supabase.table("ai_runs").select("*").order("created_at", desc=True).limit(limit)
    if status:
        query = query.eq("status", status)
    if user_id:
        query = query.eq("user_id", user_id)
    if material_id:
        query = query.eq("material_id", material_id)
    res = query.execute()
    return res.data or []


@router.get("/ai-runs/{run_id}")
def get_ai_run(
    run_id: str,
    _: Annotated[bool, Depends(require_admin_api_key)],
    supabase: Client = Depends(get_supabase),
) -> Any:
    run_res = supabase.table("ai_runs").select("*").eq("id", run_id).single().execute()
    if not run_res.data:
        raise HTTPException(status_code=404, detail="AI run not found")

    steps_res = (
        supabase.table("ai_run_steps")
        .select("*")
        .eq("run_id", run_id)
        .order("step_order", desc=False)
        .order("created_at", desc=False)
        .execute()
    )

    return {"run": run_res.data, "steps": steps_res.data or []}


@router.post("/ai-runs/{run_id}/pause")
def pause_ai_run(
    run_id: str,
    _: Annotated[bool, Depends(require_admin_api_key)],
    supabase: Client = Depends(get_supabase),
) -> Any:
    supabase.table("ai_runs").update({"status": "paused"}).eq("id", run_id).execute()
    return {"message": "paused", "run_id": run_id}


@router.post("/ai-runs/{run_id}/retry")
def retry_ai_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    _: Annotated[bool, Depends(require_admin_api_key)],
    supabase: Client = Depends(get_supabase),
    force: bool = False,
) -> Any:
    run_res = supabase.table("ai_runs").select("*").eq("id", run_id).single().execute()
    if not run_res.data:
        raise HTTPException(status_code=404, detail="AI run not found")

    material_id = run_res.data.get("material_id")
    if not material_id:
        raise HTTPException(status_code=400, detail="AI run has no material_id")

    material_res = supabase.table("materials").select("status").eq("id", material_id).single().execute()
    if material_res.data and material_res.data.get("status") == "ready" and not force:
        raise HTTPException(
            status_code=409,
            detail="Material is already ready. Pass force=true to retry anyway.",
        )

    supabase.table("materials").update({
        "status": "processing",
        "processing_step": "Retry queued",
        "processing_percentage": 0,
    }).eq("id", material_id).execute()

    background_tasks.add_task(process_material, material_id, None)
    return {"message": "retry_queued", "material_id": material_id, "retry_of_run_id": run_id}
