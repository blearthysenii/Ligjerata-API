import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class EmailDeliveryError(Exception):
    pass


def send_password_reset_code(email: str, code: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    sender = os.getenv("RESET_EMAIL_FROM", "")
    if not api_key or not sender:
        raise EmailDeliveryError("Password reset email service is not configured")

    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps({
            "from": sender,
            "to": [email],
            "subject": "Kodi për rivendosjen e fjalëkalimit",
            "html": (
                "<p>Kodi yt për Ligjerata është:</p>"
                f"<p style='font-size:28px;font-weight:700;letter-spacing:6px'>{code}</p>"
                "<p>Kodi skadon pas 10 minutash.</p>"
            ),
        }).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in {200, 201}:
                raise EmailDeliveryError("Password reset email was not accepted")
    except (HTTPError, URLError, TimeoutError) as error:
        raise EmailDeliveryError("Password reset email delivery failed") from error
