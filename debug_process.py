import os
import asyncio
from supabase import create_client
from dotenv import load_dotenv
from app.services.processing import process_material

async def debug_process():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    material_id = "76952898-5511-4d55-bbfc-9220fe418668"
    print(f"DEBUG: Manually processing material {material_id}...")
    
    try:
        await process_material(material_id, supabase)
        print("DEBUG: Processing attempted.")
    except Exception as e:
        with open("debug_log.txt", "w") as f:
            f.write(f"Process material raised: {e}\n")
            import traceback
            f.write(traceback.format_exc())
        print(f"DEBUG: Process material raised: {e}")

if __name__ == "__main__":
    asyncio.run(debug_process())
