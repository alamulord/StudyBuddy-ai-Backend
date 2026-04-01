
import os
from supabase import create_client
from dotenv import load_dotenv

# Search for .env in backend and frontend
for path in ['studyBuddy-backend/.env', 'studyBuddy-frontend/.env', '.env']:
    if os.path.exists(path):
        load_dotenv(path)
        break

url = os.environ.get("SUPABASE_URL")
# Explicitly prioritize service role key for bucket management
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

with open("diag_output.txt", "w", encoding="utf-8") as f:
    if not url or not key:
        f.write("Error: SUPABASE_URL or bucket-tier key not found in .env\n")
        exit(1)

    f.write(f"Using URL: {url}\n")
    # Mask key for safety in output
    f.write(f"Key type: {'service_role' if 'SUPABASE_SERVICE_ROLE_KEY' in os.environ else 'anon'}\n")

    supabase = create_client(url, key)

    try:
        # 1. List Buckets
        try:
            buckets = supabase.storage.list_buckets()
            f.write(f"Available buckets: {[b.name for b in buckets]}\n")
        except Exception as e:
            f.write(f"Failed to list buckets: {e}\n")
            buckets = []
        
        # 2. Check/Create 'materials' bucket
        materials_exists = any(b.name == "materials" for b in buckets)
        if not materials_exists:
            f.write("CRITICAL: 'materials' bucket does not exist! Attempting creation...\n")
            try:
                # Create as public so frontend can potentially read easily? 
                # Or private if handled via backend. Let's stick to standard private for now.
                supabase.storage.create_bucket("materials", options={"public": False})
                f.write("Successfully created 'materials' bucket.\n")
            except Exception as e:
                f.write(f"Failed to create 'materials' bucket: {e}\n")
        else:
            f.write("'materials' bucket exists.\n")
            
        # 3. Test upload (bypass RLS if using service role)
        f.write("Attempting test upload...\n")
        test_content = b"test content"
        try:
            res = supabase.storage.from_("materials").upload("test/test_file.txt", test_content, {"content-type": "text/plain"})
            f.write(f"Test upload success: {res}\n")
            # Cleanup
            supabase.storage.from_("materials").remove(["test/test_file.txt"])
            f.write("Test cleanup success.\n")
        except Exception as e:
            f.write(f"Test upload FAILED: {e}\n")

    except Exception as e:
        f.write(f"Error connecting to Supabase: {e}\n")
