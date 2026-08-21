import json
import mimetypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TranscriptionError(Exception):
    pass


class TranscriptionProvider:
    def transcribe(self, audio_url: str, language: str) -> list[dict]:
        raise NotImplementedError


class OpenAITranscriptionProvider(TranscriptionProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
        if not self.api_key:
            raise TranscriptionError("OPENAI_API_KEY is not configured")
        if self.model != "whisper-1":
            raise TranscriptionError("Timestamped transcripts currently require OPENAI_TRANSCRIPTION_MODEL=whisper-1")

    def transcribe(self, audio_url: str, language: str) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="ligjerata-transcript-") as directory:
            path = Path(directory) / "lecture.mp3"
            try:
                with urlopen(audio_url, timeout=120) as response:
                    path.write_bytes(response.read(250 * 1024 * 1024 + 1))
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                raise TranscriptionError("Audioja nuk mund të shkarkohej për transkriptim") from error
            if path.stat().st_size > 250 * 1024 * 1024:
                raise TranscriptionError("Audioja është shumë e madhe për transkriptim")
            chunks = self._split_audio(path, Path(directory))
            all_segments: list[dict] = []
            for index, chunk in enumerate(chunks):
                data = self._transcribe_chunk(chunk, language)
                offset = index * 600
                for segment in data.get("segments") or []:
                    text = str(segment.get("text", "")).strip()
                    if text:
                        all_segments.append({
                            "start_seconds": offset + max(0, int(round(segment.get("start", 0)))),
                            "end_seconds": offset + max(0, int(round(segment.get("end", 0)))),
                            "text": text,
                        })
            return all_segments

    def _split_audio(self, path: Path, directory: Path) -> list[Path]:
        pattern = directory / "chunk-%04d.mp3"
        try:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(path), "-f", "segment", "-segment_time", "600", "-c", "copy", str(pattern)],
                check=True,
                capture_output=True,
                timeout=1800,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
            raise TranscriptionError("Audioja nuk mund të ndahej për transkriptim") from error
        chunks = sorted(directory.glob("chunk-*.mp3"))
        if not chunks or any(chunk.stat().st_size > 25 * 1024 * 1024 for chunk in chunks):
            raise TranscriptionError("Audioja nuk mund të përgatitej brenda kufirit 25 MB")
        return chunks

    def _transcribe_chunk(self, path: Path, language: str) -> dict:
        payload, content_type = self._multipart(path, language)
        request = Request(
            "https://api.openai.com/v1/audio/transcriptions",
            data=payload,
            method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": content_type},
        )
        try:
            with urlopen(request, timeout=1800) as response:
                return json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise TranscriptionError("Gjenerimi i transkriptit dështoi") from error

    def _multipart(self, path: Path, language: str) -> tuple[bytes, str]:
        boundary = f"----Ligjerata{uuid.uuid4().hex}"
        parts: list[bytes] = []
        fields = {
            "model": self.model,
            "language": language,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
        }
        for name, value in fields.items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        mime = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
            + path.read_bytes()
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def get_transcription_provider() -> TranscriptionProvider:
    provider = os.getenv("TRANSCRIPTION_PROVIDER", "openai").lower()
    if provider == "openai":
        return OpenAITranscriptionProvider()
    raise TranscriptionError(f"Transcription provider '{provider}' is not supported")
