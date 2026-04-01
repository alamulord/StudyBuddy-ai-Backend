
import os
from supabase import create_client
from dotenv import load_dotenv

# Search for .env
for path in ['studyBuddy-backend/.env', 'studyBuddy-frontend/.env', '.env']:
    if os.path.exists(path):
        load_dotenv(path)
        break

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

supabase = create_client(url, key)

with open("schema_diag.txt", "w", encoding="utf-8") as f:
    tables_to_check = ["materials", "user_stats", "focus_areas", "study_activities", "flashcards", "user_settings"]
    f.write(f"Checking tables: {tables_to_check}\n")
    
    for table in tables_to_check:
        try:
            # Simple select to see if table exists
            res = supabase.table(table).select("count", count="exact").limit(1).execute()
            f.write(f"Table '{table}': EXISTS (count: {res.count})\n")
        except Exception as e:
            f.write(f"Table '{table}': ERROR/MISSING ({e})\n")
