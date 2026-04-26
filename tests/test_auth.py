import json
import pytest
from unittest.mock import MagicMock, patch
from anything_important.auth import get_access_token


def test_get_access_token_returns_token_from_valid_credentials(tmp_path):
    creds_file = tmp_path / "creds.json"
    creds_file.write_text(json.dumps({
        "client_id": "client123",
        "client_secret": "secret456",
        "refresh_token": "refresh789",
        "token_uri": "https://oauth2.googleapis.com/token",
        "token": "existing_token",
        "expiry": "2099-01-01T00:00:00Z",
    }))

    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.token = "existing_token"

    with patch("anything_important.auth.Credentials.from_authorized_user_file", return_value=mock_creds):
        token = get_access_token(str(creds_file))

    assert token == "existing_token"


def test_get_access_token_refreshes_expired_credentials(tmp_path):
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}")

    mock_creds = MagicMock()
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh789"
    mock_creds.token = "new_token"

    with (
        patch("anything_important.auth.Credentials.from_authorized_user_file", return_value=mock_creds),
        patch("anything_important.auth.Request") as mock_request,
    ):
        token = get_access_token(str(creds_file))

    mock_creds.refresh.assert_called_once()
    assert token == "new_token"
