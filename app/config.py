from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings"""
    # API Keys
    CLAUDE_API_KEY: str | None = None
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    WHATSAPP_NUMBER: str | None = None

    class Config:
        env_file = '.env'
        

@lru_cache()
def get_settings():
    return Settings()