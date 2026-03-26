# integrations/sap/business_partner.py
from .client import SAPClient

# Endpoint classique S/4HANA OData Business Partner
BUSINESS_PARTNER_ENDPOINT = "/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner"


class SAPBusinessPartnerService:
    def __init__(self):
        self.client = SAPClient()

    def list_partners(self, top=50, skip=0, search=None):
        params = {
            "$top": top,
            "$skip": skip,
            "$format": "json",
        }
        if search:
            params["$filter"] = f"contains(BusinessPartner,'{search}')"

        return self.client.request(
            method="GET",
            endpoint=BUSINESS_PARTNER_ENDPOINT,
            params=params,
            operation="LIST_BUSINESS_PARTNERS",
        )

    def get_partner(self, business_partner_id: str):
        endpoint = f"{BUSINESS_PARTNER_ENDPOINT}('{business_partner_id}')"
        return self.client.request(
            method="GET",
            endpoint=endpoint,
            params={"$format": "json"},
            operation="GET_BUSINESS_PARTNER",
        )

    def create_partner(self, payload: dict):
        return self.client.request(
            method="POST",
            endpoint=BUSINESS_PARTNER_ENDPOINT,
            payload=payload,
            operation="CREATE_BUSINESS_PARTNER",
        )

    def update_partner(self, business_partner_id: str, payload: dict):
        endpoint = f"{BUSINESS_PARTNER_ENDPOINT}('{business_partner_id}')"
        return self.client.request(
            method="PATCH",
            endpoint=endpoint,
            payload=payload,
            operation="UPDATE_BUSINESS_PARTNER",
        )