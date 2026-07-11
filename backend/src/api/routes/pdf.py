from fastapi import APIRouter, UploadFile, File

from src.rag.manager import DocumentManager

router = APIRouter()


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    metadata = await DocumentManager.create_document(file)

    return metadata