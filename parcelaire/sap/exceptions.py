# integrations/sap/exceptions.py
class SAPError(Exception):
    """Base SAP integration exception."""


class SAPAuthError(SAPError):
    """Authentication failure with SAP."""


class SAPRequestError(SAPError):
    """HTTP/API request failure with SAP."""