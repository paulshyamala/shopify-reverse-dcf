"""SEC User-Agent contact, read from SEC_USER_AGENT (loaded from .env in the repo root).

SEC fair-access rules require every request to identify the requester with a
name and email, which is kept out of the code: copy .env.example to .env and
fill it in.
"""

import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
PLACEHOLDER_DOMAIN = "example.com"


@lru_cache(maxsize=None)
def sec_user_agent():
    load_dotenv(ENV_FILE)
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent or PLACEHOLDER_DOMAIN in user_agent:
        sys.exit(
            "SEC_USER_AGENT is not set (or is still the .env.example placeholder).\n"
            "SEC EDGAR requires a User-Agent with your name and email "
            "(https://www.sec.gov/os/accessing-edgar-data).\n"
            f"Copy .env.example to {ENV_FILE} and set your own contact, e.g.\n"
            "    SEC_USER_AGENT=Jane Doe jane.doe@university.edu\n"
            "or export SEC_USER_AGENT in your shell."
        )
    return user_agent
