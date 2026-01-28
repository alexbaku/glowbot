from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # API Keys
    claude_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    # Database
    database_url: str
    database_url_sync: str

    # Application Settings
    environment: str = "development"
    debug: bool = True

    # Database Pool Settings
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"
