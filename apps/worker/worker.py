import logging
import subprocess
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from google.auth.transport.requests import AuthorizedSession

from app.main import (
    Broadcast,
    SessionLocal,
    StreamDestination,
    load_credentials,
    redis_client,
    settings,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
QUEUE_NAME = "lfc-stream:broadcast-queue"


def update_broadcast(broadcast_id: int, status: str, error: str | None = None) -> None:
    with SessionLocal() as session:
        row = session.get(Broadcast, broadcast_id)
        if row is None:
            return
        row.status = status
        if status == "running" and row.started_at is None:
            row.started_at = datetime.now(timezone.utc)
        if status in ("completed", "failed", "stopped"):
            row.ended_at = datetime.now(timezone.utc)
        row.error_message = error
        session.commit()


def run_broadcast(broadcast_id: int) -> None:
    process = None
    upstream = None
    drive_session = None
    stop_key = f"lfc-stream:stop:{broadcast_id}"
    try:
        with SessionLocal() as session:
            broadcast = session.get(Broadcast, broadcast_id)
            if broadcast is None or broadcast.status != "queued":
                return
            destination = session.get(StreamDestination, broadcast.destination_id)
            if destination is None:
                raise RuntimeError("The selected streaming destination no longer exists.")
            source_id = broadcast.drive_file_id
            encrypted_url = destination.encrypted_rtmp_url

        if not settings.token_encryption_key:
            raise RuntimeError("Token encryption is not configured.")
        output_url = Fernet(settings.token_encryption_key.encode()).decrypt(
            encrypted_url.encode()
        ).decode()
        credentials = load_credentials()
        drive_session = AuthorizedSession(credentials)
        media_url = (
            "https://www.googleapis.com/drive/v3/files/"
            + source_id
            + "?alt=media"
        )
        upstream = drive_session.get(
            media_url,
            stream=True,
            timeout=(15, 45),
        )
        if upstream.status_code != 200:
            raise RuntimeError(
                f"Google Drive media request failed with HTTP {upstream.status_code}."
            )

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-re",
            "-i", "pipe:0",
            "-map", "0:v:0",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-g", "60",
            "-b:v", "4500k",
            "-maxrate", "4500k",
            "-bufsize", "9000k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-f", "flv",
            output_url,
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        update_broadcast(broadcast_id, "running")
        logging.info("Broadcast %s started.", broadcast_id)

        for chunk in upstream.iter_content(chunk_size=256 * 1024):
            if redis_client.get(stop_key):
                break
            if not chunk:
                continue
            if process.poll() is not None:
                raise RuntimeError("FFmpeg stopped before the source video ended.")
            try:
                process.stdin.write(chunk)
            except (BrokenPipeError, OSError):
                raise RuntimeError("FFmpeg could not continue processing the source video.")

        stopped = bool(redis_client.get(stop_key))
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        try:
            return_code = process.wait(timeout=25)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                return_code = process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait(timeout=5)

        if stopped:
            update_broadcast(broadcast_id, "stopped")
            logging.info("Broadcast %s stopped.", broadcast_id)
        elif return_code == 0:
            update_broadcast(broadcast_id, "completed")
            logging.info("Broadcast %s completed.", broadcast_id)
        else:
            raise RuntimeError("FFmpeg exited with a non-zero status.")
    except Exception as exc:
        logging.error("Broadcast %s failed: %s", broadcast_id, str(exc))
        update_broadcast(broadcast_id, "failed", str(exc)[:450])
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if upstream:
            upstream.close()
        if drive_session:
            drive_session.close()
        redis_client.delete(stop_key)


def main() -> None:
    logging.info("LFC Stream FFmpeg worker is ready.")
    while True:
        try:
            item = redis_client.blpop(QUEUE_NAME, timeout=5)
            if not item:
                continue
            _, value = item
            try:
                broadcast_id = int(value)
            except ValueError:
                logging.warning("Ignoring malformed broadcast queue item.")
                continue
            run_broadcast(broadcast_id)
        except Exception:
            logging.exception("Worker loop error; retrying shortly.")
            time.sleep(3)


if __name__ == "__main__":
    main()
