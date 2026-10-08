import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Lovely Tech POS System"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://lovely_pos:change_me@localhost:5432/lovely_tech_pos"
    secret_key: str = "development-only-change-me"
    session_timeout_admin_minutes: int = 5
    session_timeout_cashier_minutes: int = 60
    session_absolute_timeout_admin_hours: int = 12
    session_absolute_timeout_cashier_hours: int = 12
    critical_reauth_required: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,tauri://localhost,http://tauri.localhost"
    backup_root: str = "./backups"
    pg_dump_bin: str = "pg_dump"
    pg_restore_bin: str = "pg_restore"
    psql_bin: str = "psql"
    google_drive_rclone_remote: str = ""
    google_drive_backup_path: str = "Lovely-Tech-POS"
    rclone_bin: str = "rclone"
    require_verified_backup_for_close: bool = True
    app_version: str = "0.4.0"
    protocol_version: str = "1.0.0"
    api_version: str = "1"
    branch_code: str = "MAIN"
    instance_id_file: str = "C:/ProgramData/LovelyTechPOS/server-data/instance.json"
    model_config = SettingsConfigDict(env_file=os.getenv("LTPOS_ENV_FILE", ".env"), extra="ignore")

settings = Settings()


def validate_production_settings() -> None:
    if settings.app_env.lower() == "production":
        secret = settings.secret_key
        if secret == "development-only-change-me" or "change_me" in secret.lower() or len(secret) < 32:
            raise RuntimeError("Production SECRET_KEY must be changed (unique, at least 32 characters)")
        if "change_me" in settings.database_url.lower():
            raise RuntimeError("Production DATABASE_URL must be configured")
