from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Wheel"
    debug: bool = False
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def allowed_origins(self) -> list[str]:
        return list(dict.fromkeys([*self.cors_origins, self.frontend_url]))


settings = Settings()
