from pathlib import Path
import shutil
from fastapi import UploadFile


BASE_UPLOAD_DIR = Path("uploads/users")


class FileManager:

    @staticmethod
    async def save_pdf(file: UploadFile, user_id: str = "user_001"):

        pdf_dir = BASE_UPLOAD_DIR / user_id / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)

        file_path = pdf_dir / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return file_path