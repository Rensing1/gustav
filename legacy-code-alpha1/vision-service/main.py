from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import os
import time
from vision_processor import process_vision_base64

app = FastAPI(title="GUSTAV Vision Service", version="1.0.0")
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class VisionRequest(BaseModel):
    file_data: str  # Base64-encoded file content
    file_type: str
    original_filename: str = "unknown"

class VisionResponse(BaseModel):
    text: str
    success: bool
    processing_time: float
    error: str = None

@app.post("/extract-text", response_model=VisionResponse)
async def extract_text(request: VisionRequest):
    """
    Extrahiert Text aus Base64-encoded Datei mittels Ollama Vision API.
    
    Args:
        request: VisionRequest mit file_data (Base64), file_type, original_filename
        
    Returns:
        VisionResponse mit extrahiertem Text und Metadaten
    """
    start_time = time.time()
    
    try:
        logger.info(f"[VISION-SERVICE] Processing {request.file_type.upper()} file: {request.original_filename}")
        logger.info(f"[VISION-SERVICE] Base64 data length: {len(request.file_data)} chars")
        
        # Prozessiere die Base64-Datei mit der isolierten Vision-Processing-Logik
        extracted_text = process_vision_base64(request.file_data, request.file_type, request.original_filename)
        
        processing_time = time.time() - start_time
        
        # Prüfe ob Text erfolgreich extrahiert wurde
        if extracted_text and not extracted_text.startswith("[Fehler") and extracted_text != "[KEIN TEXT ERKENNBAR]":
            logger.info(f"[VISION-SERVICE] ✅ SUCCESS - Extracted {len(extracted_text)} chars in {processing_time:.2f}s")
            return VisionResponse(
                text=extracted_text,
                success=True,
                processing_time=processing_time
            )
        else:
            logger.warning(f"[VISION-SERVICE] ⚠️ No text extracted: {extracted_text}")
            return VisionResponse(
                text=extracted_text or "[KEIN TEXT ERKENNBAR]",
                success=False,
                processing_time=processing_time,
                error="Keine Texterkennung möglich"
            )
            
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Vision processing failed: {str(e)}"
        logger.error(f"[VISION-SERVICE] ❌ ERROR after {processing_time:.2f}s: {error_msg}")
        
        return VisionResponse(
            text="[Fehler bei der Verarbeitung]",
            success=False,
            processing_time=processing_time,
            error=error_msg
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "GUSTAV Vision Service"}

@app.get("/")
async def root():
    """Root endpoint mit Service-Info"""
    return {
        "service": "GUSTAV Vision Service",
        "version": "1.0.0",
        "endpoints": {
            "extract_text": "/extract-text (POST)",
            "health": "/health (GET)"
        }
    }