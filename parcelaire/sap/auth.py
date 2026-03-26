# integrations/sap/auth.py
import time
import requests
from django.conf import settings
from .exceptions import SAPAuthError


class SAPOAuthClient:
    _token = None
    _expires_at = 0

    @classmethod
    def get_access_token(cls) -> str:
        now = time.time()

        if cls._token and now < cls._expires_at - 60:
            return cls._token

        response = requests.post(
            settings.SAP_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.SAP_CLIENT_ID, settings.SAP_CLIENT_SECRET),
            timeout=settings.SAP_TIMEOUT,
            verify=settings.SAP_VERIFY_SSL,
            headers={"Accept": "application/json"},
        )

        if response.status_code >= 400:
            raise SAPAuthError(
                f"OAuth authentication failed: {response.status_code} - {response.text}"
            )

        data = response.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))

        if not access_token:
            raise SAPAuthError("No access_token returned by SAP.")

        cls._token = access_token
        cls._expires_at = now + expires_in
        return cls._token