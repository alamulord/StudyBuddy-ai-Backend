import os
import sys
import json
from supabase import create_client
from dotenv import load_dotenv

# Try to find .env starting from current directory
if os.path.exists('.env'):
    load_dotenv('.env')
elif os.path.exists('studyBuddy-backend/.env'):
    load_dotenv('studyBuddy-backend/.env')
else:
    print("CRITICAL: .env file NOT FOUND")
    sys.exit(1)

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase = create_client(url, key)

print(f"Connecting to: {url}")

expected_schema = {
    "materials": ["id", "user_id", "title", "subject", "type", "storage_path", "status", "goal", "exam_date", "summary", "transcription"],
    "user_stats": ["user_id", "exam_readiness", "current_streak", "best_streak", "mastery_score"],
    "user_settings": ["user_id", "target_exam", "ai_personality", "daily_goal_minutes", "preferences"],
    "flashcards": ["id", "material_id", "user_id", "front", "back", "interval", "repetition", "easiness_factor"]
}

with open("full_schema_diag.txt", "w", encoding="utf-8") as f:
    for table, columns in expected_schema.items():
        f.write(f"\n=== Checking Table: {table} ===\n")
        try:
            # Check table existence
            res = supabase.table(table).select("*").limit(0).execute()
            f.write(f"Table '{table}' EXISTS.\n")
            
            # Check each column
            for col in columns:
                try:
                    supabase.table(table).select(col).limit(0).execute()
                    f.write(f"  Column '{col}': OK\n")
                except Exception as e:
                    f.write(f"  Column '{col}': MISSING or ERROR ({e})\n")
        except Exception as e:
            f.write(f"Table '{table}' MISSING or ERROR: {e}\n")

print("Full schema diagnosis written to full_schema_diag.txt")
