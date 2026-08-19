from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "TestPilot AI Python Backend"
    environment: str = "development"
    backend_port: int = 3001
    backend_url: str = "http://localhost:3001"
    frontend_url: str = "http://localhost:3000"
    
    groq_api_key: str = Field(default="dummy-groq-key")
    groq_model: str = Field(default="openai/gpt-oss-120b")
    jwt_secret: str = Field(default="super-secret-jwt-key-min-32-characters")
    github_client_id: str = Field(default="")
    github_client_secret: str = Field(default="")
    
    artifacts_dir: str = "./artifacts"
    repos_dir: str = "./repos"

    class Config:
        env_file = [".env", "../../.env", "../.env"]
        extra = "ignore"

settings = Settings()
