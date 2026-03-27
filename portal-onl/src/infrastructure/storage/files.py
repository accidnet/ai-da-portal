from pathlib import Path

from fastapi import UploadFile


async def save_upload_file(file: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    destination.write_bytes(content)
    await file.seek(0)
