#!/usr/bin/env python3
"""
Database initialization script for GlowBot
Creates all database tables
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging

from app.config import Settings
from app.database import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Initialize the database"""
    try:
        logger.info("Starting database initialization...")
        settings = Settings()
        logger.info(f"Database URL: {settings.database_url}")

        await init_db()
        logger.info("✅ Database initialized successfully!")

    except Exception as e:
        logger.error(f"❌ Error initializing database: {str(e)}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
