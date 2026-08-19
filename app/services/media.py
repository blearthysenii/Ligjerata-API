import ipaddress
import json
import socket
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.services.storage import StorageUploadError, upload_public_mp3


MAX_MEDIA_BYTES = 250 * 1024 * 1024
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac",
    ".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi",
}
ALLOWED_MIME_PREFIXES = ("audio/", "video/")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class MediaProcessingError(Exception):
    pass


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_remote_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise MediaProcessingError("Linku nuk është i vlefshëm.")

    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or default_port,
        )
    except socket.gaierror as error:
        raise MediaProcessingError("Adresa e linkut nuk mund të gjendet.") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise MediaProcessingError("Linku nuk lejohet për arsye sigurie.")

    return parsed.geturl()


def is_youtube_url(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in YOUTUBE_HOSTS


def run_command(command: list[str], error_message: str, timeout: int = 1800) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise MediaProcessingError(error_message) from error


def probe_media(file_path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration,format_name:stream=codec_type",
                "-of", "json", str(file_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as error:
        raise MediaProcessingError("Formati i medias nuk mbështetet.") from error

    if not any(stream.get("codec_type") == "audio" for stream in data.get("streams", [])):
        raise MediaProcessingError("Media nuk përmban audio.")
    return data


def convert_to_mp3(source_path: Path, output_path: Path) -> int:
    probe_media(source_path)
    run_command(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(source_path),
            "-vn", "-codec:a", "libmp3lame", "-b:a", "192k",
            "-ar", "44100", "-ac", "2", str(output_path),
        ],
        "Konvertimi i medias në MP3 dështoi.",
    )
    data = probe_media(output_path)
    try:
        duration = int(round(float(data["format"]["duration"])))
    except (KeyError, TypeError, ValueError) as error:
        raise MediaProcessingError("Kohëzgjatja e audios nuk u përcaktua.") from error
    if duration <= 0:
        raise MediaProcessingError("Audioja e përgatitur është bosh.")
    return duration


def download_direct_media(url: str, destination: Path) -> None:
    opener = build_opener(SafeRedirectHandler())
    request = Request(url, headers={"User-Agent": "Ligjerata-Media-Ingest/1.0"})
    try:
        with opener.open(request, timeout=60) as response, destination.open("wb") as output:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_MEDIA_BYTES:
                raise MediaProcessingError("Skedari është më i madh se 250 MB.")
            total = 0
            while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_MEDIA_BYTES:
                    raise MediaProcessingError("Skedari është më i madh se 250 MB.")
                output.write(chunk)
    except MediaProcessingError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        raise MediaProcessingError("Shkarkimi i medias dështoi.") from error


def download_youtube_audio(url: str, directory: Path) -> Path:
    template = str(directory / "youtube-source.%(ext)s")
    run_command(
        [
            sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-warnings",
            "--remote-components", "ejs:github",
            "--extractor-args", "youtube:player_client=web_embedded",
            "--cache-dir", str(directory / "yt-dlp-cache"),
            "--max-filesize", str(MAX_MEDIA_BYTES), "-f", "bestaudio/best",
            "-o", template, url,
        ],
        "Shkarkimi i audios nga YouTube dështoi.",
    )
    candidates = list(directory.glob("youtube-source.*"))
    if not candidates or candidates[0].stat().st_size > MAX_MEDIA_BYTES:
        raise MediaProcessingError("Media nuk u shkarkua ose është shumë e madhe.")
    return candidates[0]


def process_and_upload(source_path: Path) -> dict:
    output_path = source_path.parent / "prepared-audio.mp3"
    duration = convert_to_mp3(source_path, output_path)
    object_name = f"{uuid.uuid4().hex}.mp3"
    try:
        audio_url = upload_public_mp3(output_path, object_name)
    except StorageUploadError as error:
        raise MediaProcessingError(str(error)) from error
    return {
        "audio_url": audio_url,
        "duration_seconds": duration,
        "filename": object_name,
    }


def ingest_url(url: str) -> dict:
    safe_url = validate_remote_url(url)
    with tempfile.TemporaryDirectory(prefix="ligjerata-media-") as temp_name:
        directory = Path(temp_name)
        if is_youtube_url(safe_url):
            source_path = download_youtube_audio(safe_url, directory)
        else:
            extension = Path(urlparse(safe_url).path).suffix.lower()
            source_path = directory / f"remote-source{extension if extension in ALLOWED_EXTENSIONS else '.media'}"
            download_direct_media(safe_url, source_path)
        return process_and_upload(source_path)


def validate_upload_metadata(filename: str, content_type: str | None) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise MediaProcessingError("Ky format skedari nuk mbështetet.")
    if content_type and not (
        content_type.startswith(ALLOWED_MIME_PREFIXES)
        or content_type == "application/octet-stream"
    ):
        raise MediaProcessingError("Lloji i skedarit nuk mbështetet.")
    return extension


def ingest_uploaded_path(source_path: Path) -> dict:
    if source_path.stat().st_size > MAX_MEDIA_BYTES:
        raise MediaProcessingError("Skedari është më i madh se 250 MB.")
    return process_and_upload(source_path)
