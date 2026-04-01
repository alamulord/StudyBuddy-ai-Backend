from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import Annotated, Any
from app.core.deps import get_current_user, get_supabase
from app.schemas.material import Material
from supabase import Client
from app.services.processing import process_material

router = APIRouter()

@router.post("/upload", response_model=Material)
async def upload_material(
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    subject: str = Form(None),
    goal: str = Form(None),
    exam_date: str = Form(None),
    type: str = Form(...)
) -> Any:
    """
    Upload a new study material (PDF, Video, etc.).
    Steps:
    1. Upload file to Supabase Storage ('materials' bucket).
    2. Create record in 'materials' table.
    3. Trigger background processing.
    """
    
    # 1. Upload to Storage
    try:
        print(f"[{datetime.now().time()}] Upload Request: {title} ({file.filename})")
        file_content = await file.read()
        print(f"[{datetime.now().time()}] File read complete: {len(file_content)} bytes")
        
        import uuid
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else "bin"
        file_path = f"{current_user.id}/{uuid.uuid4()}.{file_ext}"
        
        print(f"[{datetime.now().time()}] Uploading to Supabase Storage: {file_path}")
        # 'materials' bucket must exist!
        supabase.storage.from_("materials").upload(file_path, file_content, {"content-type": file.content_type})
        print(f"[{datetime.now().time()}] Storage upload success.")
    except Exception as e:
        print(f"[{datetime.now().time()}] Storage upload failure: {e}")
        # If storage upload fails, return error
        raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {str(e)}")

    # 2. Insert into Database
    try:
        print(f"[{datetime.now().time()}] Inserting material record into database...")
        material_data = {
            "user_id": current_user.id,
            "title": title,
            "subject": subject,
            "type": type,
            "storage_path": file_path,
            "status": "processing",
            "goal": goal,
            "exam_date": exam_date if exam_date else None
        }
        
        result = supabase.table("materials").insert(material_data).execute()
        
        if not result.data:
             print(f"[{datetime.now().time()}] Database insert failed (no data)")
             raise HTTPException(status_code=500, detail="Database insert failed (no data returned)")
        
        material_record = result.data[0]
        print(f"[{datetime.now().time()}] Database insert success. ID: {material_record.get('id')}")
        
        # 3. Trigger Background Processing
        print(f"[{datetime.now().time()}] Triggering background task...")
        background_tasks.add_task(process_material, material_record['id'], supabase)
        print(f"[{datetime.now().time()}] Background task triggered.")
             
        return material_record
        
    except Exception as e:
        print(f"[{datetime.now().time()}] Database/Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{material_id}/archive")
def soft_delete_material(
    material_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Soft delete a material (archive it).
    """
    try:
        print(f"[{datetime.now().time()}] Attempting soft delete for material: {material_id}")
        update_data = {
            "is_archived": True,
            "archived_at": datetime.now().isoformat()
        }
        result = supabase.table("materials").update(update_data).eq("id", material_id).eq("user_id", current_user.id).execute()
        
        if not result.data:
            with open("debug_log.txt", "a") as f:
                f.write(f"[{datetime.now().time()}] Soft delete failed: Material {material_id} not found or unauthorized for user {current_user.id}\n")
            raise HTTPException(status_code=404, detail=f"Material {material_id} not found or unauthorized for user {current_user.id}")
        
        with open("debug_log.txt", "a") as f:
            f.write(f"[{datetime.now().time()}] Soft delete success for material: {material_id}\n")
            
        print(f"[{datetime.now().time()}] Soft delete success for material: {material_id}")
        return {"message": "Material archived successfully"}
    except Exception as e:
        print(f"[{datetime.now().time()}] Soft delete exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{material_id}/permanent")
def permanent_delete_material(
    material_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Permanently delete a material.
    """
    try:
        print(f"[{datetime.now().time()}] Permanent delete request: material_id={material_id}, user_id={current_user.id}")
        
        # 1. Delete associated flashcards first
        fc_res = supabase.table("flashcards").delete().eq("material_id", material_id).execute()
        print(f"[{datetime.now().time()}] Flashcards deleted: {len(fc_res.data) if fc_res.data else 0}")
        
        # 2. Delete material
        result = supabase.table("materials").delete().eq("id", material_id).eq("user_id", current_user.id).execute()
        
        if not result.data:
            print(f"[{datetime.now().time()}] Permanent delete failed - NOT FOUND in DB: material_id={material_id}")
            raise HTTPException(status_code=404, detail="Material not found or already deleted")
            
        print(f"[{datetime.now().time()}] Permanent delete success from DB: {material_id}")
        return {"message": "Material permanently deleted"}
    except Exception as e:
        print(f"[{datetime.now().time()}] Permanent delete exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{material_id}", response_model=Material)
def get_material(
    material_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Get a specific material by ID.
    """
    try:
        result = supabase.table("materials").select("*").eq("id", material_id).eq("user_id", current_user.id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Material not found")
        return result.data
    except Exception as e:
        raise HTTPException(status_code=404, detail="Material not found")

@router.post("/{material_id}/restore")
def restore_material(
    material_id: str,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    print(f"[{datetime.now().time()}] ENTER: restore_material ID={material_id}")
    """
    Restore an archived material.
    """
    try:
        update_data = {
            "is_archived": False,
            "archived_at": None
        }
        result = supabase.table("materials").update(update_data).eq("id", material_id).eq("user_id", current_user.id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Material not found")
            
        return {"message": "Material restored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=list[Material])
def list_materials(
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)],
    is_archived: bool = False,
) -> Any:
    """
    List all materials for the current user. 
    By default returns active materials (is_archived=False).
    """
    try:
        # Default to False unless explicitly requested
        query = supabase.table("materials").select("*").eq("user_id", current_user.id)
        
        # Explicit check for boolean to avoid confusion
        if is_archived:
             query = query.eq("is_archived", True)
        else:
             # Default behavior: Show only active
             # We check specifically for false or null (though default is false in db)
             query = query.eq("is_archived", False)
             
        result = query.order('created_at', desc=True).execute()
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{material_id}", response_model=Material)
async def update_material(
    material_id: str,
    material_update: dict,
    current_user: Annotated[Any, Depends(get_current_user)],
    supabase: Annotated[Client, Depends(get_supabase)]
) -> Any:
    """
    Update a material's progress or details.
    """
    try:
        # Filter allowed fields to prevent overwriting critical data
        allowed_fields = [
            "title", "subject", "goal", "exam_date", 
            "current_page", "total_pages", "last_position_seconds", 
            "readiness_score", "last_study_session", "study_sessions_count",
            "progress_metadata"
        ]
        update_data = {k: v for k, v in material_update.items() if k in allowed_fields}
        
        if not update_data:
             raise HTTPException(status_code=400, detail="No valid fields to update")

        result = supabase.table("materials").update(update_data).eq("id", material_id).eq("user_id", current_user.id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Material not found")
            
        return result.data[0]
    except Exception as e:
        print(f"Update error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
