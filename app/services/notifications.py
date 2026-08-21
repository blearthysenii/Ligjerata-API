import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_new_lecture_notifications(tokens: list[str], lecture_id: int, title: str, speaker: str) -> None:
    """Best-effort Expo delivery; publishing must succeed even if push delivery fails."""
    messages = [
        {
            "to": token,
            "sound": "default",
            "title": "Ligjëratë e re",
            "body": f"{speaker} — {title}",
            "data": {
                "lecture_id": str(lecture_id),
                "url": f"ligjeratamobile://lecture/{lecture_id}",
            },
        }
        for token in tokens
        if token.startswith("ExponentPushToken[") or token.startswith("ExpoPushToken[")
    ]
    if not messages:
        return

    for start in range(0, len(messages), 100):
        request = Request(
            EXPO_PUSH_URL,
            data=json.dumps(messages[start:start + 100]).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                response.read()
        except (HTTPError, URLError, TimeoutError) as error:
            logger.warning("Expo push delivery failed: %s", type(error).__name__)
