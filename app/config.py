from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # API Keys
    claude_api_key: str
    kelet_api_key: str
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

    # Model settings
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # iHerb affiliate — full search URL template.
    # {query} is replaced with URL-encoded search terms.
    # Swap this single value when your affiliate program is approved.
    # Current value uses referral code; update to your affiliate deep-link when ready.
    iherb_search_template: str = "https://il.iherb.com/search?query={query}&rcode=VZH480"

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

