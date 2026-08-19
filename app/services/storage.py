import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class StorageUploadError(Exception):
    pass


def upload_public_mp3(file_path: Path, object_name: str) -> str:
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "lectures-audio").strip()

    if not supabase_url or not service_key or not bucket:
        raise StorageUploadError(
            "Supabase Storage nuk është konfiguruar në server."
        )

    encoded_path = quote(f"{bucket}/{object_name}", safe="/")
    upload_url = f"{supabase_url}/storage/v1/object/{encoded_path}"
    request = Request(
        upload_url,
        data=file_path.read_bytes(),
        method="POST",
        headers={
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Content-Type": "audio/mpeg",
            "x-upsert": "false",
        },
    )

    try:
        with urlopen(request, timeout=600) as response:
            if response.status not in {200, 201}:
                raise StorageUploadError("Ngarkimi në storage dështoi.")
    except HTTPError as error:
        raise StorageUploadError(
            f"Ngarkimi në Supabase Storage dështoi (HTTP {error.code})."
        ) from error
    except (URLError, TimeoutError) as error:
        raise StorageUploadError("Ngarkimi në Supabase Storage dështoi.") from error

    return (
        f"{supabase_url}/storage/v1/object/public/"
        f"{quote(bucket, safe='')}/{quote(object_name, safe='')}"
    )
