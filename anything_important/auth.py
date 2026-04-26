from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def get_access_token(credentials_file: str) -> str:
    creds = Credentials.from_authorized_user_file(credentials_file)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds.token
