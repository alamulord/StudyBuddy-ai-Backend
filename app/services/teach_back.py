import json
from app.services.ai.llm_client import generate_content
from app.services.ai.prompts import TEACH_BACK_PROMPT
from app.core.deps import get_supabase

async def evaluate_teach_back(
    user_id: str,
    material_id: str,
    topic: str,
    explanation: str,
    personality: str = "encouraging"
):
    supabase = get_supabase()
    
    # 1. Fetch material content for reference
    material_res = supabase.table("materials").select("transcription").eq("id", material_id).execute()
    if not material_res.data:
        raise Exception("Material not found")
    
    content = material_res.data[0]["transcription"]
    
    # 2. AI Evaluation
    prompt = TEACH_BACK_PROMPT.format(personality=personality)
    
    ai_input = [
        prompt,
        f"Reference Material Context:\n{content or 'No reference available.'}",
        f"Student Chosen Topic: {topic}",
        f"Student Explanation to evaluate:\n{explanation}"
    ]
    
    # Use flash for faster/more stable responses
    ai_response = await generate_content(ai_input, model_name="gemini-1.5-flash")
    
    # 3. Parse result with improved robustness
    try:
        # AI sometimes adds intro text or varying block markers
        json_str = ai_response
        if "{" in json_str:
            json_str = json_str[json_str.find("{"):json_str.rfind("}")+1]
        
        result = json.loads(json_str)
        
        # Ensure mastery_score is a valid integer/float
        mastery = result.get("mastery_score", 0)
        if isinstance(mastery, str):
            # Strip non-numeric chars in case AI returned "(85)" or "85%"
            import re
            nums = re.findall(r'\d+', mastery)
            mastery = int(nums[0]) if nums else 0
        
        # 4. Update Topic Mastery
        supabase.table("topic_mastery").upsert({
            "user_id": user_id,
            "topic": topic,
            "mastery_percentage": mastery,
            "material_id": material_id,
            "last_updated": "now()"
        }, on_conflict="user_id,topic,material_id").execute()
        
        return result
        
    except Exception as e:
        print(f"Error parsing teach-back JSON: {e}")
        print(f"Raw AI Response: {ai_response}")
        # Return a fallback result instead of crashing the whole frontend
        return {
            "mastery_score": 0,
            "feedback_summary":f"Evaluation error: {str(e)}. Please try again.",
            "strong_points": [],
            "weak_points": ["Evaluation failure"],
            "suggested_review_topics": [topic]
        }
