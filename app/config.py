from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    # API Keys
    CLAUDE_API_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    WHATSAPP_NUMBER: str

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings() # type: ignore