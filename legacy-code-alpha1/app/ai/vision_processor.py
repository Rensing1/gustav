# Copyright (c) 2025 GUSTAV Contributors  
# SPDX-License-Identifier: MIT

"""
Vision Processor für Bild- und PDF-Verarbeitung

Verarbeitet hochgeladene Dateien (JPG, PNG, PDF) und extrahiert Text
mittels Gemma3 Vision-Capabilities über DSPy.
"""

import io
import os
import hashlib
import tempfile
import logging
import time
import json
import base64
from pathlib import Path
from PIL import Image, ImageFile
from typing import Dict, Tuple, Optional
from supabase import Client
import ollama

# DSPy-Integration für Phase 1
try:
    from .deprecated.programs import VisionTextExtractor
    from .config import VISION_MODEL, get_lm_provider
    import dspy
    HAS_DSPY = True
except ImportError:
    HAS_DSPY = False
    logging.warning("DSPy not available - falling back to direct Ollama calls")

# PDF-Support
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logging.warning("PyMuPDF not installed - PDF support disabled")

# Enable truncated image loading für robustere Verarbeitung
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger(__name__)


def extract_text_with_dspy_vision(file_bytes: bytes, filename: str, model_name: str = None) -> str:
    """
    Phase 1: DSPy-basierte Vision-Extraktion mit Base64-String (DSPy 2.5.43 compatible).
    Nutzt VisionTextExtractor DSPy-Module mit Base64-kodiertem Bild.
    """
    if not HAS_DSPY:
        logger.warning("[DSPy-Vision] DSPy nicht verfügbar - Fallback auf Ollama-Direct")
        return extract_text_with_ollama_direct(file_bytes, filename)
    
    start_time = time.time()
    effective_model = model_name or VISION_MODEL
    
    try:
        logger.info(f"[DSPy-Vision] Processing {filename} with model: {effective_model}")
        logger.info(f"[DSPy-Vision] File size: {len(file_bytes)} bytes")
        
        # DSPy 3.x: Direkt mit Bytes arbeiten (kein Base64 nötig)
        logger.info(f"[DSPy-Vision] Using DSPy 3.x with direct image bytes: {len(file_bytes)} bytes")
        
        # LM-Provider für Vision-Model erstellen
        logger.info(f"[DSPy-Vision] Creating LM provider for model: {effective_model}")
        vision_lm = get_lm_provider(model_alias=effective_model)
        if not vision_lm:
            logger.error(f"[DSPy-Vision] Konnte LM-Provider für {effective_model} nicht erstellen")
            return "[Fehler: Model nicht verfügbar]"
        logger.info(f"[DSPy-Vision] LM provider created successfully for {effective_model}")
        
        # DSPy-Module initialisieren
        extractor = VisionTextExtractor(model_name=effective_model)
        
        # DSPy-Kontext mit Vision-Model setzen
        logger.info(f"[DSPy-Vision] About to call DSPy with image bytes")
        try:
            with dspy.context(lm=vision_lm):
                result = extractor.forward(image_bytes=file_bytes)
        except Exception as dspy_error:
            logger.error(f"[DSPy-Vision] DSPy call failed: {dspy_error}")
            # Log the full error for debugging
            import traceback
            logger.error(f"[DSPy-Vision] Full traceback: {traceback.format_exc()}")
            raise
        
        duration = time.time() - start_time
        
        if hasattr(result, 'extracted_text') and result.extracted_text:
            extracted_text = result.extracted_text.strip()
            logger.info(f"[DSPy-Vision] ✅ SUCCESS in {duration:.2f}s - {len(extracted_text)} chars")
            logger.info(f"[DSPy-Vision] Text preview: {extracted_text[:200]}...")
            return extracted_text
        else:
            logger.warning(f"[DSPy-Vision] ⚠️ Leere Response nach {duration:.2f}s")
            return "[KEIN TEXT ERKENNBAR]"
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[DSPy-Vision] ❌ Fehler nach {duration:.2f}s: {type(e).__name__}: {e}")
        # Fallback zu bewährter Methode
        logger.info("[DSPy-Vision] Falling back to direct Ollama...")
        return extract_text_with_ollama_direct(file_bytes, filename)
    finally:
        # Cleanup nicht nötig für Bytes-Objekt
        pass

def extract_text_with_ollama_library(image_path: str) -> str:
    """
    Extrahiert Text aus Bild via Ollama Python Library.
    Nutzt ollama.generate() mit direkten Dateipfaden für Gemma3 Vision.
    """
    start_time = time.time()
    try:
        # Detaillierte Logs
        file_size = Path(image_path).stat().st_size
        logger.info(f"[VISION] Processing image: {image_path}")
        logger.info(f"[VISION] File size: {file_size} bytes")
        logger.info(f"[VISION] Image type: {Path(image_path).suffix}")
        
        # Vereinfachter Prompt für deutsche Handschrift-Transkription
        # Komplexer Prompt verursacht Halluzinationen bei Gemma3
        transcription_prompt = """Transkribiere den handschriftlichen Text in diesem Bild exakt.

Regeln:
- Schreibe nur den Text, der wirklich im Bild steht
- Behalte deutsche Umlaute (ä, ö, ü, ß)
- Markiere unleserliche Stellen mit [UNLESERLICH]
- Keine Erklärungen oder Kommentare"""

        # Timeout aus Umgebungsvariable verwenden
        timeout_seconds = int(os.environ.get("AI_TIMEOUT", 60))
        
        # Ollama Base URL für Docker-Container
        ollama_base_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        
        # Ollama Client mit Custom Base URL
        client = ollama.Client(host=ollama_base_url)
        
        logger.info(f"[VISION] Using ollama.generate() with timeout={timeout_seconds}s")
        
        # PRIMARY: ollama.generate() - funktioniert mit Gemma3 Vision + direkter Dateipfad
        response = client.generate(
            model="gemma3:12b",
            prompt=transcription_prompt,
            images=[image_path],  # Direkter Dateipfad ohne Base64!
            options={
                "temperature": 0.05,  # Sehr niedrig für präzise Transkription
                "top_p": 0.8
            }
        )
        
        duration = time.time() - start_time
        extracted_text = response.get("response", "").strip()
        
        logger.info(f"[VISION] Ollama Library responded in {duration:.2f}s")
        logger.info(f"[VISION] Extracted text length: {len(extracted_text)} chars")
        
        if extracted_text:
            # Log ersten 200 Zeichen des extrahierten Texts
            logger.info(f"[VISION] Text preview: {extracted_text[:200]}...")
            return extracted_text
        else:
            logger.warning("[VISION] Ollama returned empty response")
            return "[KEIN TEXT ERKENNBAR]"
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[VISION] Processing failed after {duration:.2f}s: {type(e).__name__}: {e}")
        
        # Fallback auf alte HTTP-basierte Implementierung
        logger.info("[VISION] Falling back to HTTP-based implementation...")
        return extract_text_with_optimized_http(image_path)


def extract_text_with_openwebui_format(file_bytes: bytes, filename: str, timeout: int = None) -> str:
    """
    OpenWebUI-kompatible Vision-Processing für bestehende Pipeline.
    Nutzt /api/chat mit messages[] Format für bessere Kompatibilität.
    """
    import base64
    import requests
    import sys
    
    # Timeout aus Environment Variable laden (Default: 120s)
    if timeout is None:
        timeout = int(os.environ.get("AI_TIMEOUT", 120))
    
    start_time = time.time()
    
    # GPU Stats vor Processing (AMD-kompatibel)
    gpu_stats_before = None
    try:
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts'))
        from monitor_amd_gpu import get_amd_gpu_stats
        gpu_stats_before = get_amd_gpu_stats()
        if gpu_stats_before:
            for gpu_id, stats in gpu_stats_before.items():
                logger.info(f"[GPU-BEFORE] {gpu_id}: {stats['vram_used_mb']}MB/{stats['vram_total_mb']}MB ({stats['vram_usage_percent']}%)")
    except Exception as e:
        logger.debug(f"GPU stats before vision failed: {e}")
        gpu_stats_before = None
    
    try:
        logger.info(f"[VISION-OPENWEBUI] Processing file: {filename}")
        logger.info(f"[VISION-OPENWEBUI] File size: {len(file_bytes)} bytes ({len(file_bytes)/1024:.1f}KB)")
        logger.info(f"[VISION-OPENWEBUI] Using timeout: {timeout}s")
        
        # Base64 Encoding
        encode_start = time.time()
        base64_image = base64.b64encode(file_bytes).decode('utf-8')
        encode_time = time.time() - encode_start
        logger.info(f"[VISION-OPENWEBUI] Base64 encoding took {encode_time:.3f}s")
        
        # KRITISCH: OpenWebUI Message-Format verwenden
        payload = {
            'model': 'gemma3:12b',
            'messages': [{  # messages statt prompt!
                'role': 'user',
                'content': '''Du bist ein Transkriptionsassistent für deutsche Texte.
            
AUFGABE:
- Wandle den handschriftlichen Text im Bild in maschinenlesbaren Text um.
- Übertrage den Text so exakt wie möglich.
- Markiere unleserliche Stellen mit [UNLESERLICH].

AUSGABEFORMAT:
- Nur der transkribierte Text.
- Keine Erklärungen oder Kommentare.''',
                'images': [base64_image]  # Als Liste!
            }],
            'stream': False,
            'options': {'temperature': 0.1}
        }
        
        # KRITISCH: /api/chat statt /api/generate
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        
        # Detaillierte Request-Logs für Debugging
        logger.info(f"[VISION-OPENWEBUI] Sending request to {ollama_url}/api/chat")
        logger.info(f"[API-REQUEST] Model: {payload['model']}")
        logger.info(f"[API-REQUEST] Messages count: {len(payload['messages'])}")
        logger.info(f"[API-REQUEST] Images count: {len(payload['messages'][0]['images'])}")
        logger.info(f"[API-REQUEST] Base64 size: {len(payload['messages'][0]['images'][0])} chars")
        logger.info(f"[API-REQUEST] Stream: {payload['stream']}")
        logger.info(f"[API-REQUEST] Temperature: {payload['options']['temperature']}")
        
        request_start = time.time()
        response = requests.post(f'{ollama_url}/api/chat', json=payload, timeout=timeout)
        request_time = time.time() - request_start
        
        logger.info(f"[API-RESPONSE] HTTP Status: {response.status_code}")
        logger.info(f"[API-RESPONSE] Request took: {request_time:.2f}s")
        logger.info(f"[API-RESPONSE] Response size: {len(response.text)} chars")

        # Cleanup Base64 aus Memory
        del base64_image
        
        if response.status_code == 200:
            result = response.json()
            # KRITISCH: message.content statt response
            content = result.get('message', {}).get('content', '').strip()
            
            duration = time.time() - start_time
            
            # GPU Stats nach Processing
            try:
                gpu_stats_after = get_amd_gpu_stats()
                if gpu_stats_after:
                    for gpu_id, stats in gpu_stats_after.items():
                        logger.info(f"[GPU-AFTER] {gpu_id}: {stats['vram_used_mb']}MB/{stats['vram_total_mb']}MB ({stats['vram_usage_percent']}%)")
                        if gpu_stats_before and gpu_id in gpu_stats_before:
                            vram_diff = stats['vram_used_mb'] - gpu_stats_before[gpu_id]['vram_used_mb']
                            logger.info(f"[GPU-DIFF] {gpu_id}: VRAM changed by {vram_diff:+d}MB during vision processing")
            except Exception as e:
                logger.debug(f"GPU stats after vision failed: {e}")
            
            logger.info(f"[VISION-OPENWEBUI] ✅ SUCCESS in {duration:.2f}s - extracted {len(content)} chars")
            logger.info(f"[API-RESPONSE] Response structure: {list(result.keys())}")
            
            if content:
                logger.info(f"[VISION-OPENWEBUI] Text preview: {content[:200]}...")
                logger.info(f"[VISION-OPENWEBUI] Full response JSON keys: {list(result.keys())}")
                return content
            else:
                logger.warning("[VISION-OPENWEBUI] Empty response from Ollama")
                logger.warning(f"[DEBUG] Full response: {result}")
                return "[KEIN TEXT ERKENNBAR]"
        else:
            duration = time.time() - start_time
            logger.error(f"[VISION-OPENWEBUI] HTTP Error {response.status_code} after {duration:.2f}s")
            logger.error(f"[VISION-OPENWEBUI] Response headers: {dict(response.headers)}")
            logger.error(f"[VISION-OPENWEBUI] Response: {response.text[:500]}")
            return f"[Fehler: HTTP {response.status_code}]"
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        logger.error(f"[VISION-OPENWEBUI] Timeout after {duration:.2f}s")
        return "[Fehler: Zeitüberschreitung bei der Verarbeitung]"
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[VISION-OPENWEBUI] Error after {duration:.2f}s: {type(e).__name__}: {e}")
        return "[Fehler bei der Verarbeitung]"


def extract_text_with_optimized_http(image_path: str) -> str:
    """
    Optimierte HTTP-Implementation mit effizientem Base64-Handling.
    Nutzt /api/generate für Gemma3 Vision.
    """
    import base64
    import requests
    
    start_time = time.time()
    try:
        # Datei-Info loggen BEVOR Base64-Konvertierung
        file_size = Path(image_path).stat().st_size
        logger.info(f"[VISION] Processing image: {Path(image_path).name}")
        logger.info(f"[VISION] File size: {file_size} bytes ({file_size/1024:.1f}KB)")
        
        # Streaming Base64-Encoding für große Dateien
        logger.info("[VISION] Converting to base64...")
        encode_start = time.time()
        
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
            img_base64 = base64.b64encode(img_data).decode()
        
        encode_duration = time.time() - encode_start
        logger.info(f"[VISION] Base64 encoding took {encode_duration:.3f}s, size: {len(img_base64)} chars")
        
        # Vereinfachter Prompt - reduziert Halluzinationen
        transcription_prompt = """Transkribiere den handschriftlichen Text in diesem Bild exakt.

Regeln:
- Schreibe nur den Text, der wirklich im Bild steht
- Behalte deutsche Umlaute (ä, ö, ü, ß)
- Markiere unleserliche Stellen mit [UNLESERLICH]
- Keine Erklärungen oder Kommentare"""

        # Timeout und URL
        timeout_seconds = int(os.environ.get("AI_TIMEOUT", 60))
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
        
        logger.info(f"[VISION] Sending request to {ollama_url}/api/generate with timeout={timeout_seconds}s")
        
        # HTTP Request mit direktem requests.post() (ohne Session)
        response = requests.post(f"{ollama_url}/api/generate", json={
            "model": "gemma3:12b",
            "prompt": transcription_prompt,
            "images": [img_base64],
            "stream": False,
            "options": {
                "temperature": 0.05,  # Niedrig für präzise Transkription
                "top_p": 0.8
            }
        }, timeout=timeout_seconds)
        
        # Cleanup Base64 aus Memory (GC-Hint)
        del img_base64, img_data
        
        if response.status_code == 200:
            result = response.json()
            extracted_text = result.get("response", "").strip()
            duration = time.time() - start_time
            
            logger.info(f"[VISION] ✅ SUCCESS - Total: {duration:.2f}s (encode: {encode_duration:.3f}s)")
            logger.info(f"[VISION] Extracted text length: {len(extracted_text)} chars")
            
            if extracted_text:
                logger.info(f"[VISION] Text preview: {extracted_text[:200]}...")
                return extracted_text
            else:
                logger.warning("[VISION] ⚠️ Empty response from Ollama")
                return "[KEIN TEXT ERKENNBAR]"
        else:
            duration = time.time() - start_time
            logger.error(f"[VISION] ❌ HTTP Error after {duration:.2f}s - Status: {response.status_code}")
            logger.error(f"[VISION] Response: {response.text[:500]}")
            return "[Fehler bei der Verarbeitung]"
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        logger.error(f"[VISION] ⏰ TIMEOUT after {duration:.2f}s")
        return "[Fehler: Zeitüberschreitung bei der Verarbeitung]"
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[VISION] 💥 Error after {duration:.2f}s: {type(e).__name__}: {e}")
        return "[Fehler bei der Verarbeitung]"
    finally:
        # Cleanup Base64 aus Memory (GC-Hint) falls noch nicht erledigt
        pass


class RobustImageProcessor:
    """
    Produktionsreifer Image Processor für DSPy Vision-API.
    Unterstützt JPG, PNG und PDF-Dateien.
    """
    
    def __init__(self, temp_dir="/tmp/gustav_vision", max_size=None):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True, mode=0o700)  # Secure temp directory
        self.max_size = max_size
        self.logger = logger
        
        # Cleanup alte Temp-Files beim Start
        self._cleanup_old_temp_files()
    
    def _cleanup_old_temp_files(self):
        """Entfernt Temp-Files älter als 1 Stunde"""
        import time
        current_time = time.time()
        
        try:
            for file_path in self.temp_dir.glob("processed_*.jpg"):
                if current_time - file_path.stat().st_mtime > 3600:  # 1 Stunde
                    file_path.unlink()
                    self.logger.debug(f"Cleaned up old temp file: {file_path}")
        except Exception as e:
            self.logger.warning(f"Error during temp file cleanup: {e}")
    
    def prepare_file_for_ollama(self, file_bytes: bytes, file_type: str, 
                               original_filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Konvertiert beliebige Dateien zu normalisierten JPEG-Bildern.
        Unterstützt JPG, PNG und PDF.
        
        Returns:
            tuple: (temp_file_path, None) oder (None, None) bei Fehler
        """
        try:
            file_type_lower = file_type.lower()
            
            if file_type_lower == 'pdf':
                if not HAS_PYMUPDF:
                    raise Exception("PDF-Verarbeitung nicht verfügbar - PyMuPDF fehlt")
                return self._process_pdf(file_bytes, original_filename)
            else:
                return self._process_image(file_bytes, file_type, original_filename)
                
        except Exception as e:
            self.logger.error(f"File processing failed for {original_filename}: {e}")
            return None, None
    
    def _process_pdf(self, pdf_bytes: bytes, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """PDF zu Image Konvertierung mit PyMuPDF"""
        pdf_doc = None
        try:
            # 1. PDF öffnen
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            if len(pdf_doc) == 0:
                raise Exception("PDF hat keine Seiten")
            
            # Log PDF-Info
            self.logger.info(f"Processing PDF: {filename} with {len(pdf_doc)} pages")
            
            # 2. Erste Seite als Image rendern
            first_page = pdf_doc[0]
            
            # 3. Render-Parameter für gute OCR-Qualität
            # 2x Zoom für bessere Auflösung bei Handschrift
            matrix = fitz.Matrix(2.0, 2.0)
            pix = first_page.get_pixmap(matrix=matrix)
            
            # 4. Pixmap zu PIL Image
            img_data = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_data))
            
            self.logger.info(f"PDF page rendered to image: {pil_image.size}, {pil_image.mode}")
            
            # 5. Standard Image Processing anwenden
            processed_image = self._normalize_image(pil_image)
            
            # 6. Als JPEG speichern
            file_hash = hashlib.md5(pdf_bytes).hexdigest()[:8]
            temp_filename = f"processed_pdf_{file_hash}.jpg"
            temp_path = self.temp_dir / temp_filename
            
            processed_image.save(temp_path, format='JPEG', quality=85, optimize=True)
            
            # 7. Return temp path für direkte Ollama-API  
            self.logger.info(f"Successfully processed PDF: {filename}")
            return str(temp_path), None
            
        except Exception as e:
            self.logger.error(f"PDF processing failed for {filename}: {e}")
            return None, None
        finally:
            if pdf_doc:
                pdf_doc.close()
    
    def _process_image(self, file_bytes: bytes, file_type: str, 
                      original_filename: str) -> Tuple[Optional[str], Optional[str]]:
        """Verarbeitet JPG/PNG Bilder"""
        try:
            # 1. Unique temp filename generieren
            file_hash = hashlib.md5(file_bytes).hexdigest()[:8]
            temp_filename = f"processed_{file_hash}.jpg"
            temp_path = self.temp_dir / temp_filename
            
            # 2. PIL Image aus bytes erstellen + normalisieren
            image_buffer = io.BytesIO(file_bytes)
            with Image.open(image_buffer) as pil_image:
                self.logger.info(f"Original image: {pil_image.format}, {pil_image.size}, {pil_image.mode}")
                
                # 3. Normalisierung für DSPy-Stabilität
                processed_image = self._normalize_image(pil_image)
                
                # 4. Als JPEG speichern (DSPy-kompatibel)
                processed_image.save(temp_path, format='JPEG', quality=85, optimize=True)
                
                # 5. Return temp path für direkte Ollama-API
                self.logger.info(f"Successfully processed image from {original_filename}")
                return str(temp_path), None
                
        except Exception as e:
            self.logger.error(f"Image processing failed for {original_filename}: {e}")
            return None, None
    
    def _normalize_image(self, pil_image: Image.Image) -> Image.Image:
        """Normalisiert PIL Images für optimale DSPy-Verarbeitung"""
        
        # 1. Farbmodus-Konvertierung (eliminiert Transparenz/Paletten-Probleme)
        if pil_image.mode in ('RGBA', 'LA'):
            # Transparenz auf weißen Hintergrund
            background = Image.new('RGB', pil_image.size, (255, 255, 255))
            if pil_image.mode == 'RGBA':
                background.paste(pil_image, mask=pil_image.split()[-1])
            else:
                # LA mode: L with Alpha
                background.paste(pil_image, mask=pil_image.split()[-1])
            pil_image = background
        elif pil_image.mode == 'P':
            # Palette zu RGB
            pil_image = pil_image.convert('RGB')
        elif pil_image.mode not in ('RGB', 'L'):
            # Alle anderen Modi zu RGB
            pil_image = pil_image.convert('RGB')
        
        # 2. Größen-Optimierung (Context Length Management für Gemma3)
        # Original-Auflösung beibehalten wenn max_size=None
        if self.max_size is not None:
            if pil_image.size[0] > self.max_size[0] or pil_image.size[1] > self.max_size[1]:
                pil_image.thumbnail(self.max_size, Image.Resampling.LANCZOS)
            self.logger.info(f"Resized image to {pil_image.size}")
        
        # 3. Qualitäts-Optimierung
        if pil_image.mode == 'RGB':
            # DPI normalisieren für konsistente Ergebnisse
            pil_image.info['dpi'] = (72, 72)
        
        return pil_image
    
    def cleanup_temp_file(self, temp_path: str):
        """Räumt temporäre Dateien auf"""
        try:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
                self.logger.debug(f"Cleaned up temp file: {temp_path}")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup {temp_path}: {e}")


def extract_text_via_vision_service(file_bytes: bytes, file_type: str, original_filename: str) -> str:
    """
    Extrahiert Text über Vision-Service HTTP-API mit Base64-Übertragung.
    Eliminiert DSPy-Threading-Probleme durch externe Service-Architektur.
    """
    import requests
    import base64
    
    start_time = time.time()
    vision_service_url = os.environ.get("VISION_SERVICE_URL", "http://vision_service:8000")
    
    try:
        logger.info(f"[VISION] Using Vision-Service at {vision_service_url}")
        logger.info(f"[VISION] Processing {file_type.upper()} file: {original_filename}")
        logger.info(f"[VISION] File size: {len(file_bytes)} bytes")
        
        # Base64-Encoding der Datei-Daten
        encode_start = time.time()
        file_data_base64 = base64.b64encode(file_bytes).decode('utf-8')
        encode_time = time.time() - encode_start
        logger.info(f"[VISION] Base64 encoding took {encode_time:.3f}s, size: {len(file_data_base64)} chars")
        
        # HTTP POST zu Vision-Service mit Base64-Daten
        response = requests.post(f"{vision_service_url}/extract-text", json={
            "file_data": file_data_base64,
            "file_type": file_type,
            "original_filename": original_filename
        }, timeout=90)  # Großzügiger Timeout für Vision-Processing
        
        if response.status_code == 200:
            result = response.json()
            processing_time = time.time() - start_time
            
            if result.get("success"):
                logger.info(f"[VISION] ✅ SUCCESS via Vision-Service in {processing_time:.2f}s")
                logger.info(f"[VISION] Extracted {len(result.get('text', ''))} characters")
                return result.get("text", "[KEIN TEXT ERKENNBAR]")
            else:
                error_msg = result.get("error", "Unknown error")
                logger.warning(f"[VISION] ⚠️ Vision-Service failed: {error_msg}")
                return result.get("text", "[KEIN TEXT ERKENNBAR]")
        else:
            logger.error(f"[VISION] HTTP Error {response.status_code}: {response.text[:500]}")
            return "[Fehler: Vision-Service nicht erreichbar]"
            
    except requests.exceptions.Timeout:
        processing_time = time.time() - start_time
        logger.error(f"[VISION] ⏰ Vision-Service Timeout after {processing_time:.2f}s")
        return "[Fehler: Zeitüberschreitung bei der Verarbeitung]"
    except requests.exceptions.ConnectionError:
        logger.error("[VISION] ❌ Connection Error: Vision-Service not available")
        return "[Fehler: Vision-Service nicht verfügbar]"
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"[VISION] 💥 Vision-Service Error after {processing_time:.2f}s: {type(e).__name__}: {e}")
        return f"[Fehler bei der Verarbeitung: {str(e)}]"


def extract_text_with_ollama_direct(file_bytes: bytes, filename: str, timeout: int = None) -> str:
    """
    LEGACY: Alte /api/generate Implementation (Fallback).
    Basiert auf WORKING_VISION_CODE.md - direkte HTTP-API ohne Vision Service.
    """
    import base64
    import requests
    
    # Timeout aus Environment Variable laden (Default: 120s)
    if timeout is None:
        timeout = int(os.environ.get("AI_TIMEOUT", 120))
    
    start_time = time.time()
    
    try:
        logger.info(f"[VISION-DIRECT] Processing file: {filename}")
        logger.info(f"[VISION-DIRECT] File size: {len(file_bytes)} bytes")
        logger.info(f"[VISION-DIRECT] Using timeout: {timeout}s")
        
        # Transkriptions-Prompt (bewährt aus WORKING_VISION_CODE.md)
        prompt = '''Du bist ein Transkriptionsassistent für deutsche Texte.

AUFGABE:
- Wandle den handschriftlichen Text im Bild in maschinenlesbaren Text um.
- Übertrage den Text so exakt wie möglich.
- Markiere unleserliche Stellen mit [UNLESERLICH].

AUSGABEFORMAT:
- Nur der transkribierte Text.
- Keine Erklärungen oder Kommentare.'''

        # Base64 Encoding
        encode_start = time.time()
        jpg_b64 = base64.b64encode(file_bytes).decode()
        encode_time = time.time() - encode_start
        logger.info(f"[VISION-DIRECT] Base64 encoding took {encode_time:.3f}s")
        
        # LEGACY API-CALL mit /api/generate
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        
        logger.info(f"[VISION-DIRECT] Sending request to {ollama_url}/api/generate")
        
        response = requests.post(f'{ollama_url}/api/generate', json={
            'model': 'gemma3:12b',
            'prompt': prompt,
            'images': [jpg_b64],
            'stream': False,
            'options': {
                'temperature': 0.1
            }
        }, timeout=timeout)

        # Cleanup Base64 aus Memory
        del jpg_b64
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('response', '')
            
            duration = time.time() - start_time
            logger.info(f"[VISION-DIRECT] ✅ SUCCESS in {duration:.2f}s - extracted {len(content)} chars")
            
            if content:
                logger.info(f"[VISION-DIRECT] Text preview: {content[:200]}...")
                return content
            else:
                logger.warning("[VISION-DIRECT] Empty response from Ollama")
                return "[KEIN TEXT ERKENNBAR]"
        else:
            duration = time.time() - start_time
            logger.error(f"[VISION-DIRECT] HTTP Error {response.status_code} after {duration:.2f}s")
            logger.error(f"[VISION-DIRECT] Response: {response.text[:500]}")
            return f"[Fehler: HTTP {response.status_code}]"
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        logger.error(f"[VISION-DIRECT] Timeout after {duration:.2f}s")
        return "[Fehler: Zeitüberschreitung bei der Verarbeitung]"
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[VISION-DIRECT] Error after {duration:.2f}s: {type(e).__name__}: {e}")
        return "[Fehler bei der Verarbeitung]"


def process_vision_submission_hybrid(supabase: Client, submission_data: Dict) -> Dict:
    """
    HYBRID: OpenWebUI-Format + bestehende Storage-Pipeline.
    Kombiniert bewährte Pipeline mit stabiler Vision-API.
    """
    start_time = time.time()
    
    if not submission_data.get('file_path'):
        logger.info("[VISION-HYBRID] No file_path in submission_data, skipping vision processing")
        return submission_data
    
    try:
        # 1. Download von Storage (bestehend)
        file_path = submission_data['file_path']
        file_type = submission_data.get('file_type', 'jpg').lower()
        original_filename = submission_data.get('original_filename', 'upload.jpg')
        
        logger.info(f"[VISION-HYBRID] Starting processing for {file_type.upper()} file: {file_path}")
        
        download_start = time.time()
        file_bytes = supabase.storage.from_('submissions').download(file_path)
        download_time = time.time() - download_start
        
        if not file_bytes:
            logger.error(f"[VISION-HYBRID] Could not download file: {file_path}")
            submission_data['text'] = "[Fehler: Datei nicht gefunden]"
            submission_data['processing_stage'] = 'error'
            submission_data['processing_error'] = "File not found in storage"
            return submission_data
        
        logger.info(f"[VISION-HYBRID] Downloaded {len(file_bytes)} bytes in {download_time:.2f}s")
        
        # 2. PDF zu Bild konvertieren falls nötig (VERBESSERT: max_size=None)
        if file_type == 'pdf':
            logger.info("[VISION-HYBRID] Converting PDF to image...")
            processor = RobustImageProcessor(max_size=None)  # KEINE Komprimierung!
            temp_path, error = processor.prepare_file_for_ollama(file_bytes, 'pdf', original_filename)
            
            if not temp_path:
                logger.error(f"[VISION-HYBRID] PDF conversion failed: {error}")
                submission_data['text'] = "[Fehler: PDF-Konvertierung fehlgeschlagen]"
                submission_data['processing_stage'] = 'error'
                submission_data['processing_error'] = "PDF conversion failed"
                return submission_data
            
            # Lade konvertiertes Bild
            with open(temp_path, 'rb') as f:
                file_bytes = f.read()
            
            # Cleanup temp file
            processor.cleanup_temp_file(temp_path)
        
        # 3. NEU: OpenWebUI-Format für Vision-Processing
        vision_start = time.time()
        extracted_text = extract_text_with_openwebui_format(
            file_bytes=file_bytes,
            filename=original_filename
        )
        vision_time = time.time() - vision_start
        
        # 4. Ergebnis verarbeiten (bestehend)
        if extracted_text and not extracted_text.startswith("[Fehler"):
            submission_data['text'] = extracted_text
            submission_data['extracted_text'] = extracted_text  # Für Kompatibilität
            submission_data['processing_stage'] = 'text_extracted'
            submission_data['vision_processed'] = True
            
            # Erweiterte Metrics mit detailliertem Staging
            submission_data['processing_metrics'] = {
                'download_time_ms': int(download_time * 1000),
                'vision_time_ms': int(vision_time * 1000),
                'total_time_ms': int((time.time() - start_time) * 1000),
                'text_length': len(extracted_text),
                'model_used': 'gemma3:12b',
                'method': 'openwebui_chat',
                'api_format': 'openwebui_chat'
            }
            
            # Detaillierte Processing-Stages für Debugging
            submission_data['processing_stages'] = {
                'upload_completed': {'timestamp': start_time, 'status': 'success'},
                'download_started': {'timestamp': start_time + 0.001, 'status': 'success'},
                'download_completed': {'timestamp': start_time + download_time, 'status': 'success', 'file_size_bytes': len(file_bytes)},
                'vision_started': {'timestamp': start_time + download_time, 'status': 'success', 'api_endpoint': '/api/chat'},
                'vision_completed': {'timestamp': time.time(), 'status': 'success', 'text_chars': len(extracted_text)}
            }
            
            total_time = time.time() - start_time
            logger.info(f"[VISION-HYBRID] ✅ SUCCESS - Total: {total_time:.2f}s, extracted {len(extracted_text)} chars")
        else:
            # Fehlerfall
            submission_data['text'] = extracted_text if extracted_text else "[Text nicht erkennbar]"
            submission_data['processing_stage'] = 'error'
            submission_data['processing_error'] = "Vision extraction failed"
            submission_data['vision_processed'] = False
            
            total_time = time.time() - start_time
            logger.warning(f"[VISION-HYBRID] ⚠️ FAILED after {total_time:.2f}s. Result: {extracted_text}")
        
        return submission_data
            
    except Exception as e:
        logger.error(f"[VISION-HYBRID] Processing failed for {submission_data.get('file_path')}: {e}")
        submission_data['text'] = "[Fehler bei der Verarbeitung]"
        submission_data['processing_stage'] = 'error'
        submission_data['processing_error'] = str(e)
        submission_data['vision_processed'] = False
        return submission_data


def process_vision_submission_direct(supabase: Client, submission_data: Dict) -> Dict:
    """
    VEREINFACHTE Version: Verarbeitet Dateien direkt via Ollama ohne Vision Service.
    Basiert auf bewährtem Code aus WORKING_VISION_CODE.md.
    
    Unterstützt: JPG, PNG, PDF
    """
    start_time = time.time()
    
    if not submission_data.get('file_path'):
        logger.info("[VISION-DIRECT] No file_path in submission_data, skipping vision processing")
        return submission_data
    
    try:
        # 1. Download von Storage
        file_path = submission_data['file_path']
        file_type = submission_data.get('file_type', 'jpg').lower()
        original_filename = submission_data.get('original_filename', 'upload.jpg')
        
        logger.info(f"[VISION-DIRECT] Starting processing for {file_type.upper()} file: {file_path}")
        
        download_start = time.time()
        file_bytes = supabase.storage.from_('submissions').download(file_path)
        download_time = time.time() - download_start
        
        if not file_bytes:
            logger.error(f"[VISION-DIRECT] Could not download file: {file_path}")
            submission_data['text'] = "[Fehler: Datei nicht gefunden]"
            submission_data['processing_stage'] = 'error'
            submission_data['processing_error'] = "File not found in storage"
            return submission_data
        
        logger.info(f"[VISION-DIRECT] Downloaded {len(file_bytes)} bytes in {download_time:.2f}s")
        
        # 2. PDF zu Bild konvertieren falls nötig
        if file_type == 'pdf':
            logger.info("[VISION-DIRECT] Converting PDF to image...")
            processor = RobustImageProcessor(max_size=None)  # Original-Auflösung beibehalten
            temp_path, error = processor.prepare_file_for_ollama(file_bytes, 'pdf', original_filename)
            
            if not temp_path:
                logger.error(f"[VISION-DIRECT] PDF conversion failed: {error}")
                submission_data['text'] = "[Fehler: PDF-Konvertierung fehlgeschlagen]"
                submission_data['processing_stage'] = 'error'
                submission_data['processing_error'] = "PDF conversion failed"
                return submission_data
            
            # Lade konvertiertes Bild
            with open(temp_path, 'rb') as f:
                file_bytes = f.read()
            
            # Cleanup temp file
            processor.cleanup_temp_file(temp_path)
        
        # 3. Direkte Ollama Vision-Verarbeitung (bewährter Code)
        vision_start = time.time()
        extracted_text = extract_text_with_ollama_direct(
            file_bytes=file_bytes,
            filename=original_filename,
            timeout=50  # 10s Buffer für 60s Worker-Timeout
        )
        vision_time = time.time() - vision_start
        
        # 4. Ergebnis verarbeiten
        if extracted_text and not extracted_text.startswith("[Fehler"):
            submission_data['text'] = extracted_text
            submission_data['extracted_text'] = extracted_text  # Für Kompatibilität
            submission_data['processing_stage'] = 'text_extracted'
            submission_data['vision_processed'] = True
            
            # Metrics speichern
            submission_data['processing_metrics'] = {
                'download_time_ms': int(download_time * 1000),
                'vision_time_ms': int(vision_time * 1000),
                'total_time_ms': int((time.time() - start_time) * 1000),
                'text_length': len(extracted_text),
                'model_used': 'gemma3:12b',
                'method': 'direct_ollama'
            }
            
            total_time = time.time() - start_time
            logger.info(f"[VISION-DIRECT] ✅ SUCCESS - Total: {total_time:.2f}s, extracted {len(extracted_text)} chars")
        else:
            # Fehlerfall
            submission_data['text'] = extracted_text if extracted_text else "[Text nicht erkennbar]"
            submission_data['processing_stage'] = 'error'
            submission_data['processing_error'] = "Vision extraction failed"
            submission_data['vision_processed'] = False
            
            total_time = time.time() - start_time
            logger.warning(f"[VISION-DIRECT] ⚠️ FAILED after {total_time:.2f}s. Result: {extracted_text}")
        
        return submission_data
            
    except Exception as e:
        logger.error(f"[VISION-DIRECT] Processing failed for {submission_data.get('file_path')}: {e}")
        submission_data['text'] = "[Fehler bei der Verarbeitung]"
        submission_data['processing_stage'] = 'error'
        submission_data['processing_error'] = str(e)
        submission_data['vision_processed'] = False
        return submission_data


def process_vision_submission_dspy(supabase: Client, submission_data: Dict) -> Dict:
    """
    NEUE DSPy-basierte Vision-Pipeline (Phase 1).
    Drop-in-Replacement für bestehende Vision-Processing-Funktionen.
    """
    start_time = time.time()
    
    if not submission_data.get('file_path'):
        logger.info("[DSPy-Vision] No file_path in submission_data, skipping vision processing")
        return submission_data
    
    try:
        # 1. Download von Storage (unverändert)
        file_path = submission_data['file_path']
        file_type = submission_data.get('file_type', 'jpg').lower()
        original_filename = submission_data.get('original_filename', 'upload.jpg')
        
        logger.info(f"[DSPy-Vision] Starting processing for {file_type.upper()} file: {file_path}")
        
        download_start = time.time()
        file_bytes = supabase.storage.from_('submissions').download(file_path)
        download_time = time.time() - download_start
        
        if not file_bytes:
            logger.error(f"[DSPy-Vision] Could not download file: {file_path}")
            submission_data['text'] = "[Fehler: Datei nicht gefunden]"
            submission_data['processing_stage'] = 'error'
            submission_data['processing_error'] = "File not found in storage"
            return submission_data
        
        logger.info(f"[DSPy-Vision] Downloaded {len(file_bytes)} bytes in {download_time:.2f}s")
        
        # 2. PDF zu Bild konvertieren falls nötig (unverändert)
        if file_type == 'pdf':
            logger.info("[DSPy-Vision] Converting PDF to image...")
            processor = RobustImageProcessor(max_size=None)
            temp_path, error = processor.prepare_file_for_ollama(file_bytes, 'pdf', original_filename)
            
            if not temp_path:
                logger.error(f"[DSPy-Vision] PDF conversion failed: {error}")
                submission_data['text'] = "[Fehler: PDF-Konvertierung fehlgeschlagen]"
                submission_data['processing_stage'] = 'error'
                submission_data['processing_error'] = "PDF conversion failed"
                return submission_data
            
            # Lade konvertiertes Bild
            with open(temp_path, 'rb') as f:
                file_bytes = f.read()
            
            # Cleanup temp file
            processor.cleanup_temp_file(temp_path)
        
        # 3. DSPy-basierte Vision-Verarbeitung (NEU!)
        vision_start = time.time()
        extracted_text = extract_text_with_dspy_vision(
            file_bytes=file_bytes,
            filename=original_filename,
            model_name=None  # Nutzt VISION_MODEL aus Config
        )
        vision_time = time.time() - vision_start
        
        # 4. Ergebnis verarbeiten (angepasst für DSPy-Metrics)
        if extracted_text and not extracted_text.startswith("[Fehler"):
            submission_data['text'] = extracted_text
            submission_data['extracted_text'] = extracted_text
            submission_data['processing_stage'] = 'text_extracted'
            submission_data['vision_processed'] = True
            
            # DSPy-Metrics
            submission_data['processing_metrics'] = {
                'download_time_ms': int(download_time * 1000),
                'vision_time_ms': int(vision_time * 1000),
                'total_time_ms': int((time.time() - start_time) * 1000),
                'text_length': len(extracted_text),
                'model_used': VISION_MODEL,
                'method': 'dspy_vision',
                'dspy_enabled': HAS_DSPY
            }
            
            total_time = time.time() - start_time
            logger.info(f"[DSPy-Vision] ✅ SUCCESS - Total: {total_time:.2f}s, extracted {len(extracted_text)} chars")
        else:
            submission_data['text'] = extracted_text if extracted_text else "[Text nicht erkennbar]"
            submission_data['processing_stage'] = 'error'
            submission_data['processing_error'] = "DSPy vision extraction failed"
            submission_data['vision_processed'] = False
            
            total_time = time.time() - start_time
            logger.warning(f"[DSPy-Vision] ⚠️ FAILED after {total_time:.2f}s. Result: {extracted_text}")
        
        return submission_data
            
    except Exception as e:
        logger.error(f"[DSPy-Vision] Processing failed for {submission_data.get('file_path')}: {e}")
        submission_data['text'] = "[Fehler bei der Verarbeitung]"
        submission_data['processing_stage'] = 'error'
        submission_data['processing_error'] = str(e)
        submission_data['vision_processed'] = False
        return submission_data

def process_vision_submission(supabase: Client, submission_data: Dict) -> Dict:
    """
    Verarbeitet Dateien über Vision-Service statt direkter DSPy-Integration.
    Erweitert submission_data um extrahierten Text.
    
    Unterstützt: JPG, PNG, PDF
    """
    start_time = time.time()
    
    if not submission_data.get('file_path'):
        logger.info("[VISION] No file_path in submission_data, skipping vision processing")
        return submission_data
    
    temp_path = None
    
    try:
        # 1. Download von Storage
        file_path = submission_data['file_path']
        file_type = submission_data.get('file_type', 'unknown')
        logger.info(f"[VISION] Starting processing for {file_type.upper()} file: {file_path}")
        
        download_start = time.time()
        file_bytes = supabase.storage.from_('submissions').download(file_path)
        download_time = time.time() - download_start
        
        if not file_bytes:
            logger.error(f"[VISION] Could not download file: {file_path}")
            submission_data['text'] = "[Fehler: Datei nicht gefunden]"
            submission_data['vision_error'] = "File not found in storage"
            return submission_data
        
        logger.info(f"[VISION] Downloaded {len(file_bytes)} bytes in {download_time:.2f}s")
        
        # 2. Vision-Analyse über HTTP-Service mit Base64-Übertragung (keine temp files nötig)
        extracted_text = extract_text_via_vision_service(
            file_bytes=file_bytes,
            file_type=file_type,
            original_filename=submission_data.get('original_filename', 'unknown')
        )
        
        # 4. Erfolgreiche Verarbeitung
        if extracted_text and extracted_text != "[KEIN TEXT ERKENNBAR]" and not extracted_text.startswith("[Fehler"):
            submission_data['text'] = extracted_text
            submission_data['vision_processed'] = True
            total_time = time.time() - start_time
            logger.info(f"[VISION] ✅ SUCCESS - Total processing time: {total_time:.2f}s, extracted {len(extracted_text)} characters")
        else:
            submission_data['text'] = "[Text nicht erkennbar]" if extracted_text == "[KEIN TEXT ERKENNBAR]" else extracted_text
            submission_data['vision_error'] = "Keine Texterkennung möglich"
            submission_data['vision_processed'] = True
            total_time = time.time() - start_time
            logger.warning(f"[VISION] ⚠️ FAILED - No text extracted after {total_time:.2f}s. Result: {extracted_text}")
        
        # 5. Metadata behalten
        submission_data['vision_metadata'] = {
            'processed_at': str(os.environ.get('TZ', 'UTC')),
            'file_type': submission_data.get('file_type'),
            'original_filename': submission_data.get('original_filename'),
            'method': 'vision_service'
        }
            
    except Exception as e:
        logger.error(f"Vision processing failed for {submission_data.get('file_path')}: {e}")
        submission_data['text'] = "[Fehler bei der Verarbeitung]"
        submission_data['vision_error'] = str(e)
        submission_data['vision_processed'] = False
    
    finally:
        # 6. Cleanup nicht mehr nötig - keine temp files im Worker
        pass
    
    return submission_data