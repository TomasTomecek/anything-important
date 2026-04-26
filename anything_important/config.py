import os
from dataclasses import dataclass


@dataclass
class Config:
    telegram_token: str
    telegram_chat_id: str
    ollama_url: str
    ollama_model: str
    check_interval: int
    gmail_credentials_file: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            check_interval=int(os.getenv("CHECK_INTERVAL", "300")),
            gmail_credentials_file=os.getenv(
                "GMAIL_CREDENTIALS_FILE", "/credentials/oauth_credentials.json"
            ),
        )
