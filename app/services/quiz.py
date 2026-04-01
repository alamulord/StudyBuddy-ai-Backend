import json
from typing import List, Optional
from app.services.ai.llm_client import generate_content
from app.services.ai.prompts import QUIZ_PROMPT
from app.core.deps import get_supabase
from pydantic import BaseModel

class QuizQuestion(BaseModel):
    question_text: str
    options: List[str]
    correct_answer: str
    explanation: str
    topic: str

async def generate_quiz_for_material(
    user_id: str,
    material_id: str,
    num_questions: int = 20,
    difficulty: str = "standard",
    target_exam: str = "SAT",
    personality: str = "encouraging"
) -> str:
    # 1. Fetch material content
    supabase = get_supabase()
    material_res = supabase.table("materials").select("content").eq("id", material_id).execute()
    if not material_res.data:
        raise Exception("Material not found")
    
    content = material_res.data[0]["content"]
    
    # 2. Generate questions via AI
    prompt = QUIZ_PROMPT.format(
        num_questions=num_questions,
        difficulty=difficulty,
        target_exam=target_exam,
        personality=personality
    )
    
    # We use Flash for speed in quiz generation
    ai_response = await generate_content([prompt, f"Material Content:\n{content}"], model_name="gemini-1.5-flash")
    
    # 3. Parse and save to DB
    try:
        # AI might return markdown blocks, clean them
        clean_json = ai_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json.replace("```json", "").replace("```", "").strip()
            
        questions_data = json.loads(clean_json)
        
        # Create Quiz entry
        quiz_res = supabase.table("quizzes").insert({
            "user_id": user_id,
            "material_id": material_id,
            "title": f"Practice Quiz: {difficulty.capitalize()}",
            "difficulty": difficulty
        }).execute()
        
        quiz_id = quiz_res.data[0]["id"]
        
        # Create Questions entries
        questions_to_insert = [
            {
                "quiz_id": quiz_id,
                "question_text": q["question_text"],
                "options": q["options"],
                "correct_answer": q["correct_answer"],
                "explanation": q["explanation"],
                "topic": q["topic"]
            }
            for q in questions_data
        ]
        
        supabase.table("quiz_questions").insert(questions_to_insert).execute()
        
        return quiz_id
        
    except Exception as e:
        print(f"Error parsing/saving quiz questions: {e}")
        print(f"AI Response was: {ai_response}")
        raise e

async def submit_quiz_attempt(
    user_id: str,
    quiz_id: str,
    answers: dict, # {question_id: selected_answer}
    time_taken: int
):
    supabase = get_supabase()
    
    # 1. Fetch correct answers
    questions_res = supabase.table("quiz_questions").select("*").eq("quiz_id", quiz_id).execute()
    questions = {q["id"]: q for q in questions_res.data}
    
    # 2. Calculate score
    score = 0
    total = len(questions)
    topic_performance = {} # {topic: [correct, total]}
    
    for q_id, selected in answers.items():
        q = questions.get(q_id)
        if not q: continue
        
        topic = q.get("topic", "General")
        if topic not in topic_performance:
            topic_performance[topic] = [0, 0]
        
        topic_performance[topic][1] += 1
        
        if selected == q["correct_answer"]:
            score += 1
            topic_performance[topic][0] += 1
            
    # 3. Save attempt
    supabase.table("quiz_attempts").insert({
        "user_id": user_id,
        "quiz_id": quiz_id,
        "score": score,
        "total_questions": total,
        "time_taken": time_taken,
        "answers": answers
    }).execute()
    
    # Detailed results for frontend
    detailed_questions = []
    for q_id, q in questions.items():
        user_answer = answers.get(q_id)
        detailed_questions.append({
            "id": q_id,
            "question_text": q["question_text"],
            "options": q["options"],
            "correct_answer": q["correct_answer"],
            "user_answer": user_answer,
            "is_correct": user_answer == q["correct_answer"],
            "explanation": q["explanation"],
            "topic": q["topic"]
        })
    
    # 4. Update Topic Mastery
    # ... existing code ...
    for topic, (correct, t_total) in topic_performance.items():
        percentage = int((correct / t_total) * 100)
        
        # Get material_id from quiz
        quiz_info = supabase.table("quizzes").select("material_id").eq("id", quiz_id).execute()
        material_id = quiz_info.data[0]["material_id"]
        
        # Upsert topic mastery
        supabase.table("topic_mastery").upsert({
            "user_id": user_id,
            "topic": topic,
            "mastery_percentage": percentage,
            "material_id": material_id,
            "last_updated": "now()"
        }, on_conflict="user_id,topic,material_id").execute()
        
    return {
        "score": score,
        "total": total,
        "percentage": int((score / total) * 100) if total > 0 else 0,
        "topic_performance": topic_performance,
        "detailed_questions": detailed_questions
    }
