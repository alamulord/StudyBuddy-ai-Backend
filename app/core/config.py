from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "StudyBuddy API"
    API_V1_STR: str = "/api/v1"
    SUPABASE_URL: str
    SUPABASE_KEY: str  # Anon key
    SUPABASE_SERVICE_ROLE_KEY: str
    GEMINI_API_KEY: str
    OPENAI_API_KEY: str
    ADMIN_API_KEY: str = ""
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
