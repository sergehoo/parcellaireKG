# integrations/sap/client.py
import requests
from django.conf import settings
# from integrations.models import IntegrationLog
from .auth import SAPOAuthClient
from .exceptions import SAPRequestError
from ..models import IntegrationLog


class SAPClient:
    def __init__(self):
        self.base_url = settings.SAP_BASE_URL.rstrip("/")

    def _headers(self):
        token = SAPOAuthClient.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(self, method, endpoint, payload=None, params=None, operation="SAP_CALL"):
        url = f"{self.base_url}{endpoint}"
        log = IntegrationLog.objects.create(
            system="SAP",
            direction="OUTBOUND",
            operation=operation,
            endpoint=url,
            method=method.upper(),
            request_payload=payload or params,
            status="PENDING",
        )

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                json=payload,
                params=params,
                headers=self._headers(),
                timeout=settings.SAP_TIMEOUT,
                verify=settings.SAP_VERIFY_SSL,
            )

            log.http_status = response.status_code

            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text}

            log.response_payload = body

            if response.status_code >= 400:
                log.status = "ERROR"
                log.error_message = response.text
                log.save(update_fields=[
                    "http_status", "response_payload", "status", "error_message"
                ])
                raise SAPRequestError(
                    f"SAP request failed [{response.status_code}] {response.text}"
                )

            log.status = "SUCCESS"
            log.save(update_fields=["http_status", "response_payload", "status"])
            return body

        except Exception as exc:
            log.status = "ERROR"
            log.error_message = str(exc)
            log.save(update_fields=["status", "error_message"])
            raise