import os
from dataclasses import dataclass


@dataclass
class Config:
    telegram_token: str
    telegram_chat_id: str
    llm_url: str
    llm_model: str
    check_interval: int
    gmail_credentials_file: str
    gmail_query: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            llm_url=os.getenv("LLM_URL", "http://localhost:11434"),
            llm_model=os.getenv("LLM_MODEL", "llama3.2"),
            check_interval=int(os.getenv("CHECK_INTERVAL", "300")),
            gmail_credentials_file=os.getenv(
                "GMAIL_CREDENTIALS_FILE", "/credentials/oauth_credentials.json"
            ),
            gmail_query=os.getenv("GMAIL_QUERY", "is:unread newer_than:5d -label:llm-says-important"),
        )
