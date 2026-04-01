import asyncio
from supabase import create_client, ClientOptions
import httpx
from app.core.config import settings

async def check_status(material_id):
    timeout = httpx.Timeout(30.0)
    httpx_client = httpx.Client(timeout=timeout)
    options = ClientOptions(httpx_client=httpx_client)
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY, options=options)
    
    try:
        data = supabase.table("materials").select("*").eq("id", material_id).single().execute()
        m = data.data
        print(f"ID: {m['id']}")
        print(f"Status: {m['status']}")
        print(f"Step: {m.get('processing_step')}")
        print(f"Percentage: {m.get('processing_percentage')}")
        if m.get('summary'):
            print(f"Summary Length: {len(m['summary'])}")
        else:
            print("Summary: None")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_status("2bb72a76-e552-491c-a72c-ad6625760bd8"))
