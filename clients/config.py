import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    jira_base_url: str
    jira_pat: str
    confluence_base_url: str
    confluence_pat: str


def load_settings(env_path: str = None) -> Settings:
    load_dotenv(env_path or os.path.join(os.path.dirname(__file__), "..", ".env"))

    required = {
        "JIRA_BASE_URL": os.getenv("JIRA_BASE_URL"),
        "JIRA_PAT": os.getenv("JIRA_PAT"),
        "CONFLUENCE_BASE_URL": os.getenv("CONFLUENCE_BASE_URL"),
        "CONFLUENCE_PAT": os.getenv("CONFLUENCE_PAT"),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in your values."
        )

    return Settings(
        jira_base_url=required["JIRA_BASE_URL"].rstrip("/"),
        jira_pat=required["JIRA_PAT"],
        confluence_base_url=required["CONFLUENCE_BASE_URL"].rstrip("/"),
        confluence_pat=required["CONFLUENCE_PAT"],
    )
