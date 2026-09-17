from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "AI Data Analyst"
    debug: bool = False
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    openai_api_key: str = ""
    # Workers pick tools and summarise numbers; a small model is enough.
    worker_model: str = "gpt-5.6-luna"
    # The interpreter writes the summary a person reads, so it gets a stronger model.
    interpreter_model: str = "gpt-5.6-terra"

    # Uploads above this are rejected. Vercel caps request bodies at 4.5 MB.
    max_upload_bytes: int = 4_500_000
    # Rows beyond this are sampled before analysis so a run fits in one request.
    max_rows: int = 200_000

    @property
    def allowed_origins(self) -> list[str]:
        return list(dict.fromkeys([*self.cors_origins, self.frontend_url]))


settings = Settings()
