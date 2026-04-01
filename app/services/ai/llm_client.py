import asyncio
import httpx
from openai import AsyncOpenAI
from app.core.config import settings
import google.generativeai as genai
from typing import List, Union, Dict, Any

# Global semaphore to prevent hitting rate limits too aggressively
_ai_semaphore = asyncio.Semaphore(1)

# Initialize OpenAI client
openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=httpx.Timeout(120.0, connect=10.0)
)

# Initialize Gemini client
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """
You are StudyBuddy AI, a world-class personal tutor. 
Your goal is to help students learn more efficiently by transforming complex materials into clear, high-quality study aids.

When asked for study notes:
- Always use professional Markdown.
- Be comprehensive but concise.
- Focus on pedagogy and clarity.

When asked for flashcards:
- Provide strictly valid JSON.
- Ensure questions stimulate active recall.
- Avoid trivial facts; focus on concepts that matter for exams.

Always adopt the user's requested personality (e.g. Encouraging, Strict, Funny) and keep their stated goals and target exams in mind.
"""

def _get_model_fallbacks(requested_model: str) -> List[Dict[str, str]]:
    """
    Get list of models to try in order, with provider and model name.
    Dynamic fallback strategy based on requested model.
    """
    clean_name = requested_model.lower().replace('models/', '')
    
    # Define fallback chains: [provider, model_name]
    if 'gemini' in clean_name:
        # Gemini requested: try Gemini first, then OpenAI
        if 'flash' in clean_name:
            return [
                {'provider': 'gemini', 'model': 'gemini-2.0-flash'},
                {'provider': 'gemini', 'model': 'gemini-flash-latest'},
                {'provider': 'openai', 'model': 'gpt-4o-mini'},
                {'provider': 'openai', 'model': 'gpt-4o'}
            ]
        else:  # pro models
            return [
                {'provider': 'gemini', 'model': 'gemini-2.5-pro'},
                {'provider': 'gemini', 'model': 'gemini-pro-latest'},
                {'provider': 'openai', 'model': 'gpt-4o'},
                {'provider': 'openai', 'model': 'gpt-4o-mini'}
            ]
    else:
        # OpenAI requested: try OpenAI first, then Gemini
        if 'mini' in clean_name or 'gpt-4o-mini' in clean_name:
            return [
                {'provider': 'openai', 'model': 'gpt-4o-mini'},
                {'provider': 'gemini', 'model': 'gemini-2.0-flash'},
                {'provider': 'gemini', 'model': 'gemini-flash-latest'},
                {'provider': 'openai', 'model': 'gpt-4o'}
            ]
        else:  # gpt-4o or other
            return [
                {'provider': 'openai', 'model': 'gpt-4o'},
                {'provider': 'gemini', 'model': 'gemini-2.5-pro'},
                {'provider': 'gemini', 'model': 'gemini-pro-latest'},
                {'provider': 'gemini', 'model': 'gemini-2.0-flash'}
            ]

def _is_quota_error(error: Exception) -> bool:
    """
    Check if error is quota/rate limit related.
    """
    error_str = str(error).lower()
    quota_indicators = [
        'quota', 'rate limit', '429', 'insufficient_quota', 
        'billing', 'usage limit', 'exceeded'
    ]
    return any(indicator in error_str for indicator in quota_indicators)

async def _call_openai(contents, model: str) -> str:
    """
    Call OpenAI API with given model.
    """
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    
    if isinstance(contents, str):
        messages.append({"role": "user", "content": contents})
    elif isinstance(contents, list):
        user_content = []
        for part in contents:
            if isinstance(part, str):
                user_content.append({"type": "text", "text": part})
            elif isinstance(part, dict) and "mime_type" in part:
                # OpenAI handles images differently, for audio/video we'd need transcribing
                pass
        
        if not user_content:
            messages.append({"role": "user", "content": str(contents)})
        else:
            messages.append({"role": "user", "content": user_content})

    response = await openai_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=4000
    )
    
    if response.choices and response.choices[0].message.content:
        return response.choices[0].message.content
    raise Exception("OpenAI returned empty response")

async def _call_gemini(contents, model: str) -> str:
    """
    Call Gemini API with given model.
    """
    gemini_model = genai.GenerativeModel(model)
    
    # Handle multimodal content for Gemini
    if isinstance(contents, str):
        prompt = f"{SYSTEM_INSTRUCTION}\n\nUser: {contents}"
    elif isinstance(contents, list):
        parts = []
        parts.append(SYSTEM_INSTRUCTION)
        parts.append("\n\nUser: ")
        
        for part in contents:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "mime_type" in part and "data" in part:
                import mimetypes
                mime_type = part["mime_type"]
                if mime_type.startswith('image/'):
                    import io
                    from PIL import Image
                    
                    img = Image.open(io.BytesIO(part["data"]))
                    parts.append(img)
                else:
                    # For audio/video, Gemini can handle directly
                    parts.append(part["data"])
        
        prompt = parts
    else:
        prompt = f"{SYSTEM_INSTRUCTION}\n\nUser: {str(contents)}"
    
    response = await gemini_model.generate_content_async(prompt)
    return response.text

async def generate_content(contents, model_name: str = 'gpt-4o-mini') -> str:
    """
    Generate content with dynamic model fallback between OpenAI and Gemini.
    Automatically switches providers on quota/rate limit errors.
    """
    async with _ai_semaphore:
        model_fallbacks = _get_model_fallbacks(model_name)
        last_error = None
        
        for model_info in model_fallbacks:
            provider = model_info['provider']
            model = model_info['model']
            
            retries = 2  # Reduced retries for faster fallback
            for attempt in range(retries):
                try:
                    from datetime import datetime
                    print(f"[{datetime.now().time()}] Trying {provider.upper()} model {model} (attempt {attempt+1})")
                    
                    if provider == 'openai':
                        result = await _call_openai(contents, model)
                    elif provider == 'gemini':
                        result = await _call_gemini(contents, model)
                    else:
                        raise ValueError(f"Unknown provider: {provider}")
                    
                    print(f"[{datetime.now().time()}] {provider.upper()} call successful with {model}")
                    return result
                    
                except Exception as e:
                    print(f"Warning: {provider.upper()} model {model} failed: {e}")
                    last_error = e
                    
                    # If it's a quota error, break to next provider immediately
                    if _is_quota_error(e):
                        print(f"Quota/rate limit detected on {provider.upper()}, switching provider...")
                        break
                    
                    # Otherwise backoff and retry same model
                    await asyncio.sleep(1 * (attempt + 1))
            
            print(f"Provider {provider.upper()} exhausted or failed. Trying next...")
        
        print(f"Critical: All providers and models failed: {last_error}")
        raise last_error
