# Copyright (c) 2025 GUSTAV Contributors  
# SPDX-License-Identifier: MIT

"""
Isolierte Vision-Processing-Logik für Vision-Service.
Extrahiert aus app/ai/vision_processor.py ohne DSPy-Threading-Konflikte.
"""

import io
import os
import hashlib
import tempfile
import logging
import time
from pathlib import Path
from PIL import Image, ImageFile
from typing import Optional, Tuple
import requests
import json

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


def extract_text_with_ollama_http_raw(file_bytes: bytes, filename: str) -> str:
    """
    EXAKT WIE GEMMA-TEST.PY - Direkte Ollama API ohne File-Processing.
    Nutzt rohe Bytes direkt als Base64 für maximum compatibility.
    """
    start_time = time.time()
    try:
        logger.info(f"[VISION] RAW processing: {filename}, {len(file_bytes)} bytes")
        
        # EXAKT DERSELBE PROMPT WIE IN GEMMA-TEST.PY
        prompt = '''Du bist ein Transkriptionsassistent für deutsche Texte.

AUFGABE:
- Wandle den hochgeladenen handschriftlichen Text (Bild/PDF) in maschinenlesbaren Text um.
- Übertrage den Text so exakt wie möglich.
- Beachte deutsche Umlaute (ä, ö, ü, ß) und Sonderzeichen.
- Erhalte die ursprüngliche Rechtschreibung, Zeichensetzung und Formatierung (Absätze, Listen, Hervorhebungen).
- Ergänze nichts, interpretiere nichts und korrigiere nichts - auch keine Rechtschreibfehler.
- Markiere unleserliche Stellen mit [UNLESERLICH].
- Markiere unsichere Stellen mit [?? unsicherer_text ??].
- WICHTIG: Vermeide Halluzinationen - schreibe ausschließlich das, was im Bild wirklich steht.

AUSGABEFORMAT:
- Nur der transkribierte Text.
- Keine zusätzlichen Erklärungen, Kommentare oder Interpretationen.'''

        # Base64 direkt aus raw bytes - KEINE IMAGE PROCESSING
        import base64
        jpg_b64 = base64.b64encode(file_bytes).decode()
        
        logger.info(f"[VISION] Base64 length: {len(jpg_b64)} chars")
        
        # KORRIGIERT: PROMPT FORMAT (nicht messages) für Gemma3 Vision
        response = requests.post('http://ollama:11434/api/generate', json={
            'model': 'gemma3:12b',
            'prompt': prompt,
            'images': [jpg_b64],
            'stream': False,
            'options': {
                'temperature': 0.05,
                'top_p': 0.8
            }
        }, timeout=300)

        duration = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            content = result.get('response', '')
            
            logger.info(f"[VISION] ✅ SUCCESS in {duration:.2f}s")
            logger.info(f"[VISION] Response length: {len(content)} chars")
            logger.info(f"[VISION] Text preview: {content[:200]}...")
            
            return content if content else "[KEIN TEXT ERKENNBAR]"
        else:
            logger.error(f"[VISION] ❌ FAILED - Status: {response.status_code}")
            logger.error(f"[VISION] Error: {response.text[:300]}")
            return f"[Fehler: HTTP {response.status_code}]"

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[VISION] 💥 ERROR after {duration:.2f}s: {e}")
        return f"[Fehler bei der Verarbeitung: {str(e)}]"


class RobustImageProcessor:
    """
    Produktionsreifer Image Processor für Vision-Service.
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
        current_time = time.time()
        
        try:
            for file_path in self.temp_dir.glob("processed_*.jpg"):
                if current_time - file_path.stat().st_mtime > 3600:  # 1 Stunde
                    file_path.unlink()
                    self.logger.debug(f"Cleaned up old temp file: {file_path}")
        except Exception as e:
            self.logger.warning(f"Error during temp file cleanup: {e}")
    
    def prepare_file_for_ollama_from_bytes(self, file_bytes: bytes, file_type: str, original_filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Konvertiert Datei-Bytes zu normalisierten JPEG-Bildern.
        Unterstützt JPG, PNG und PDF. Optimiert für Base64-Übertragung.
        
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

    def prepare_file_for_ollama(self, file_path: str, file_type: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Konvertiert beliebige Dateien zu normalisierten JPEG-Bildern.
        Unterstützt JPG, PNG und PDF. Legacy-Methode für File-Path-basierte Verarbeitung.
        
        Returns:
            tuple: (temp_file_path, None) oder (None, None) bei Fehler
        """
        try:
            # Lese Datei
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            file_type_lower = file_type.lower()
            original_filename = Path(file_path).name
            
            # Delegiere an Bytes-basierte Methode
            return self.prepare_file_for_ollama_from_bytes(file_bytes, file_type_lower, original_filename)
                
        except Exception as e:
            self.logger.error(f"File processing failed for {file_path}: {e}")
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
    
    def _process_image(self, file_bytes: bytes, file_type: str, original_filename: str) -> Tuple[Optional[str], Optional[str]]:
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
                
                # 3. Normalisierung für Vision-Service-Stabilität
                processed_image = self._normalize_image(pil_image)
                
                # 4. Als JPEG speichern
                processed_image.save(temp_path, format='JPEG', quality=85, optimize=True)
                
                # 5. Return temp path für direkte Ollama-API
                self.logger.info(f"Successfully processed image from {original_filename}")
                return str(temp_path), None
                
        except Exception as e:
            self.logger.error(f"Image processing failed for {original_filename}: {e}")
            return None, None
    
    def _normalize_image(self, pil_image: Image.Image) -> Image.Image:
        """Normalisiert PIL Images für optimale Vision-Verarbeitung"""
        
        # 1. Farbmodus-Konvertierung
        if pil_image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', pil_image.size, (255, 255, 255))
            if pil_image.mode == 'RGBA':
                background.paste(pil_image, mask=pil_image.split()[-1])
            else:
                background.paste(pil_image, mask=pil_image.split()[-1])
            pil_image = background
        elif pil_image.mode == 'P':
            pil_image = pil_image.convert('RGB')
        elif pil_image.mode not in ('RGB', 'L'):
            pil_image = pil_image.convert('RGB')
        
        # 2. Größen-Optimierung - DEAKTIVIERT für Originalqualität
        if self.max_size and (pil_image.size[0] > self.max_size[0] or pil_image.size[1] > self.max_size[1]):
            pil_image.thumbnail(self.max_size, Image.Resampling.LANCZOS)
            self.logger.info(f"Resized image to {pil_image.size}")
        else:
            self.logger.info(f"Keeping original image size: {pil_image.size} (resize disabled)")
        
        # 3. Qualitäts-Optimierung
        if pil_image.mode == 'RGB':
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


def process_vision_base64(file_data_base64: str, file_type: str, original_filename: str) -> str:
    """
    VEREINFACHT: Direkter Base64 -> Ollama ohne komplexes File-Processing.
    Exakt wie gemma-test.py - nur rohe Bytes an Ollama.
    """
    import base64
    
    try:
        # 1. Base64 zu Bytes dekodieren
        file_bytes = base64.b64decode(file_data_base64)
        logger.info(f"[VISION-SERVICE] Decoded {len(file_bytes)} bytes from Base64")
        
        # 2. DIREKT an Ollama - KEINE FILE PROCESSING
        logger.info(f"[VISION-SERVICE] RAW processing - skipping image manipulation")
        extracted_text = extract_text_with_ollama_http_raw(file_bytes, original_filename)
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Vision processing failed for {original_filename}: {e}")
        return f"[Fehler bei der Verarbeitung: {str(e)}]"


def process_vision_file(file_path: str, file_type: str) -> str:
    """
    Legacy-Funktion für File-Path-basierte Verarbeitung.
    Verwendet für Backward-Compatibility.
    """
    processor = RobustImageProcessor()
    temp_path = None
    
    try:
        # 1. File Processing (inkl. PDF Support)
        temp_path, _ = processor.prepare_file_for_ollama(file_path, file_type)
        
        if temp_path is None:
            raise Exception("File processing failed - unsupported format or corrupted file")
        
        # 2. Vision-Analyse mit Ollama Library
        logger.info(f"[VISION-SERVICE] Starting Ollama vision analysis for: {temp_path}")
        extracted_text = extract_text_with_ollama_library(temp_path)
        
        return extracted_text
        
    except Exception as e:
        logger.error(f"Vision processing failed for {file_path}: {e}")
        return f"[Fehler bei der Verarbeitung: {str(e)}]"
    
    finally:
        # 3. Cleanup (wichtig!)
        if temp_path:
            processor.cleanup_temp_file(temp_path)