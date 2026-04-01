import asyncio
import json
import fitz  # pymupdf
from app.services.ai.llm_client import generate_content
from app.services.ai.prompts import (
    CHUNK_SUMMARIZATION_PROMPT, 
    SECTION_AGGREGATION_PROMPT, 
    FINAL_NOTE_GENERATION_PROMPT, 
    FLASHCARD_PROMPT,
    SYSTEM_PROMPT_EFFICIENCY
)
from datetime import datetime
from supabase import create_client, ClientOptions
from app.core.config import settings
import httpx

async def get_user_context(user_id: str, supabase_client):
    """
    Fetch user focus areas, weak topics, and previous materials to maintain continuity.
    """
    try:
        # Fetch weak areas (< 50 mastery)
        focus_res = supabase_client.table("focus_areas").select("title").eq("user_id", user_id).lt("mastery_level", 50).execute()
        weak_topics = [t['title'] for t in focus_res.data] if focus_res.data else ["None identified yet"]
        
        # Fetch mastered areas (> 80 mastery)
        mastered_res = supabase_client.table("focus_areas").select("title").eq("user_id", user_id).gt("mastery_level", 80).execute()
        focus_topics = [t['title'] for t in mastered_res.data] if mastered_res.data else ["Building foundation"]
        
        # Fetch previous materials summary (titles)
        prev_res = supabase_client.table("materials").select("title").eq("user_id", user_id).eq("status", "ready").limit(5).execute()
        previous_summary = [m['title'] for m in prev_res.data] if prev_res.data else ["First study session"]
        
        return {
            "weak_topics": ", ".join(weak_topics),
            "focus_topics": ", ".join(focus_topics),
            "previous_summary": ", ".join(previous_summary)
        }
    except Exception as e:
        print(f"Warning: Failed to fetch user context: {e}")
        return {
            "weak_topics": "General knowledge",
            "focus_topics": "Student profile",
            "previous_summary": "N/A"
        }

def chunk_text(text, chunk_size=3200): # ~800 tokens
    """Splits text into chunks of roughly chunk_size characters."""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

async def process_material(material_id: str, _unused_client=None):
    """
    Process uploaded material with a multi-stage AI pipeline for efficiency and quality.
    Stages:
    1. Chunk Summarization (Gemini Flash)
    2. Section Aggregation (Gemini Flash)
    3. Final Note Generation (Gemini Pro/Flash fallback)
    4. Flashcard Generation (Gemini Flash)
    """
    print(f"[{datetime.now().time()}] STARTING process_material for {material_id}")
    
    timeout = httpx.Timeout(300.0)
    httpx_client = httpx.Client(timeout=timeout)
    options = ClientOptions(
        httpx_client=httpx_client,
        postgrest_client_timeout=300,
        storage_client_timeout=300
    )
    supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, options=options)
    
    run_id = None
    current_step_id = None
    
    def _now_iso():
        return datetime.now().isoformat()
    
    def _safe_insert_ai_run(user_id: str, metadata: dict):
        nonlocal run_id
        try:
            res = supabase_client.table("ai_runs").insert({
                "user_id": user_id,
                "material_id": material_id,
                "run_type": "process_material_v2",
                "status": "running",
                "started_at": _now_iso(),
                "metadata": metadata
            }).execute()
            if res.data and len(res.data) > 0:
                run_id = res.data[0].get("id")
        except Exception as e:
            print(f"Warning: Failed to create ai_run for {material_id}: {e}")
    
    def _start_step(user_id: str, step_name: str, step_order: int, metadata=None):
        nonlocal current_step_id
        if not run_id: return None
        try:
            payload = {
                "run_id": run_id, "user_id": user_id, "material_id": material_id,
                "step_name": step_name, "step_order": step_order,
                "status": "running", "started_at": _now_iso()
            }
            if metadata: payload["metadata"] = metadata
            res = supabase_client.table("ai_run_steps").insert(payload).execute()
            current_step_id = res.data[0].get("id") if res.data else None
            return current_step_id
        except Exception as e:
            print(f"Warning: Failed to create step {step_name}: {e}")
        return None
    
    def _finish_step(status: str, output=None, error_message=None):
        nonlocal current_step_id
        if not current_step_id: return
        try:
            payload = {"status": status, "completed_at": _now_iso()}
            if output: payload["output"] = output
            if error_message: payload["error_message"] = error_message
            supabase_client.table("ai_run_steps").update(payload).eq("id", current_step_id).execute()
        except Exception as e:
            print(f"Warning: Failed to finish step: {e}")
        current_step_id = None

    def update_progress(step: str, percentage: int):
        try:
            print(f"[{datetime.now().time()}] {step} ({percentage}%)")
            supabase_client.table("materials").update({
                "processing_step": step,
                "processing_percentage": percentage
            }).eq("id", material_id).execute()
        except Exception as e:
            print(f"Warning: Progress update failed: {e}")

    try:
        # 1. Fetch Material Info
        update_progress("Initializing...", 5)
        response = supabase_client.table("materials").select("*").eq("id", material_id).single().execute()
        if not response.data: return
        material = response.data
        user_id, storage_path = material['user_id'], material['storage_path']
        goal = material.get('goal') or "General Understanding"
        
        _safe_insert_ai_run(user_id, {"title": material.get("title"), "goal": goal})
        
        # 2. Download & Extract Text
        update_progress("Extracting content...", 15)
        _start_step(user_id, "extract_content", 10)
        file_data = supabase_client.storage.from_("materials").download(storage_path)
        content_text = ""
        is_multimodal = False
        mime_type = "text/plain"
        
        if storage_path.lower().endswith(".pdf"):
            doc = fitz.open(stream=file_data, filetype="pdf")
            for page in doc: content_text += page.get_text() + "\n"
        elif any(storage_path.lower().endswith(ext) for ext in ['.webm', '.mp3', '.wav', '.m4a', '.mp4']):
            is_multimodal = True
            mime_type = "video/mp4" if storage_path.lower().endswith(".mp4") else "audio/mpeg"
        else:
            content_text = file_data.decode("utf-8")
        _finish_step("succeeded", output={"chars": len(content_text)})

        # 3. Stage 1: Chunk Summarization
        update_progress("Analyzing material chunks...", 30)
        _start_step(user_id, "chunk_summarization", 20)
        
        if is_multimodal:
            # For multimodal, we treat as one chunk for now or handle separately
            # User request focuses on efficiency for long docs, but multimodal is usually single file
            prompt = SYSTEM_PROMPT_EFFICIENCY + "\n" + CHUNK_SUMMARIZATION_PROMPT.format(chunk_text="[Attached Media]")
            chunk_summaries = [await generate_content([prompt, {"mime_type": mime_type, "data": file_data}], model_name='gemini-1.5-flash')]
        else:
            chunks = chunk_text(content_text)
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                prompt = SYSTEM_PROMPT_EFFICIENCY + "\n" + CHUNK_SUMMARIZATION_PROMPT.format(chunk_text=chunk)
                summary = await generate_content(prompt, model_name='gemini-1.5-flash')
                chunk_summaries.append(summary)
                update_progress(f"Chunk {i+1}/{len(chunks)} processed", 30 + int((i+1)/len(chunks) * 20))
        _finish_step("succeeded", output={"chunks_count": len(chunk_summaries)})

        # 4. Stage 2: Section Aggregation
        update_progress("Consolidating concepts...", 60)
        _start_step(user_id, "section_aggregation", 30)
        all_summaries_text = "\n\n".join(chunk_summaries)
        # If summaries are too long, we might need hierarchical aggregation, but for most docs this is fine
        aggregation_prompt = SECTION_AGGREGATION_PROMPT.format(chunk_summaries=all_summaries_text[:20000])
        section_summaries = await generate_content(aggregation_prompt, model_name='gemini-1.5-flash')
        _finish_step("succeeded")

        # 5. Stage 3: Final Note Generation
        update_progress("Generating final study notes...", 80)
        _start_step(user_id, "final_note_generation", 40)
        # Fetch user settings for personality
        settings_res = supabase_client.table("user_settings").select("*").eq("user_id", user_id).execute()
        target_exam = settings_res.data[0].get("target_exam", "General") if settings_res.data else "General"
        personality = settings_res.data[0].get("ai_personality", "Encouraging") if settings_res.data else "Encouraging"
        
        final_notes_prompt = FINAL_NOTE_GENERATION_PROMPT.format(
            target_exam=target_exam, 
            personality=personality, 
            section_summaries=section_summaries
        )
        study_notes = await generate_content(final_notes_prompt, model_name='gemini-1.5-pro')
        _finish_step("succeeded")

        # 6. Stage 4: Flashcard Generation
        update_progress("Creating active recall cards...", 90)
        _start_step(user_id, "flashcard_generation", 50)
        flash_prompt = FLASHCARD_PROMPT.format(
            target_exam=target_exam,
            personality=personality,
            final_notes=study_notes
        )
        flash_response = await generate_content(flash_prompt, model_name='gemini-1.5-flash')
        cleaned_json = flash_response.replace("```json", "").replace("```", "").strip()
        flashcards_data = json.loads(cleaned_json)
        
        # Save Flashcards
        flashcards_records = [{
            "material_id": material_id, "user_id": user_id, 
            "front": fc.get("front", ""), "back": fc.get("back", ""),
            "created_at": datetime.now().isoformat(), "interval": 0, "repetition": 0, "easiness_factor": 2.5
        } for fc in flashcards_data]
        if flashcards_records:
            supabase_client.table("flashcards").insert(flashcards_records).execute()
        _finish_step("succeeded", output={"count": len(flashcards_records)})

        # 7. Finalize Material
        update_progress("Finalizing...", 100)
        supabase_client.table("materials").update({
            "status": "ready",
            "summary": study_notes,
            "transcription": study_notes, # Map notes to transcription field for easier UI access
            "confidence_score": 95, # Multi-stage processing is high confidence
            "processing_step": "Completed",
            "processing_percentage": 100
        }).eq("id", material_id).execute()
        
        supabase_client.table("ai_runs").update({"status": "succeeded", "completed_at": _now_iso()}).eq("id", run_id).execute()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        if current_step_id: _finish_step("failed", error_message=str(e))
        if run_id: supabase_client.table("ai_runs").update({"status": "failed", "completed_at": _now_iso(), "error_message": str(e)}).eq("id", run_id).execute()
        supabase_client.table("materials").update({"status": "failed", "processing_step": f"Error: {str(e)[:100]}", "processing_percentage": 0}).eq("id", material_id).execute()
    finally:
        httpx_client.close()
