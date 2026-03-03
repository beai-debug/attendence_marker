"""
Production Configuration for Attendance Marker System
PostgreSQL + pgvector Configuration with Automatic Setup
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL Database Configuration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "attendance_db"
    user: str = "postgres"
    password: str = "Deepdive"
    
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800  # 30 minutes
    
    # pgvector settings
    vector_dimension: int = 512  # InsightFace embedding dimension
    
    @property
    def sync_url(self) -> str:
        """Synchronous database URL for psycopg2"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        """Asynchronous database URL for asyncpg"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def admin_url(self) -> str:
        """Admin URL for creating database (connects to postgres db)"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/postgres"


@dataclass
class AppConfig:
    """Application Configuration"""
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # File storage
    data_dir: str = "data"
    faces_dir: str = "data/faces"
    attendance_crops_dir: str = "data/attendance_crops"
    temp_dir: str = "temp_uploads"
    
    # Face recognition settings
    face_detection_size: tuple = (640, 640)
    default_threshold: float = 0.3
    
    # Default session
    default_session: str = "2025-26"


# Global configuration instances
db_config = DatabaseConfig(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    database=os.getenv("POSTGRES_DB", "attendance_db"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "Deepdive"),
)

app_config = AppConfig(
    host=os.getenv("APP_HOST", "0.0.0.0"),
    port=int(os.getenv("APP_PORT", "8000")),
    debug=os.getenv("APP_DEBUG", "false").lower() == "true",
)
