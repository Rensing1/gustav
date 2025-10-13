#!/usr/bin/env python3
"""
Test Vision API mit exakt dem Prompt aus unserem Vision-Processor
"""
import requests
import base64
import time
import json
from pathlib import Path

def test_vision_with_exact_prompt(image_path: str, file_type: str):
    """Teste mit exaktem Prompt aus vision_processor.py"""
    
    # Der exakte Prompt aus unserem Code (Zeilen 59-73)
    transcription_prompt = """Du bist ein Transkriptionsassistent für deutsche Texte.

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
- Keine zusätzlichen Erklärungen, Kommentare oder Interpretationen."""

    # Bild laden und zu Base64 konvertieren
    with open(image_path, "rb") as f:
        img_data = f.read()
        img_base64 = base64.b64encode(img_data).decode()
    
    print(f"🧪 Testing {file_type.upper()}: {Path(image_path).name}")
    print(f"📊 File size: {len(img_data)} bytes")
    print(f"📊 Base64 size: {len(img_base64)} chars")
    print(f"🔤 Using EXACT prompt from vision_processor.py")
    
    start_time = time.time()
    
    try:
        response = requests.post("http://localhost:11434/api/chat", json={
            "model": "gemma3:12b",
            "messages": [{
                "role": "user",
                "content": transcription_prompt,
                "images": [img_base64]
            }],
            "stream": False,
            "options": {
                "temperature": 0.05,  # Exact same as our code
                "top_p": 0.8
            }
        }, timeout=300)  # Same timeout as our code
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("message", {}).get("content", "")
            
            print(f"✅ SUCCESS in {duration:.2f}s")
            print(f"📝 Response length: {len(content)} chars")
            print(f"📄 First 200 chars: {content[:200]}...")
            print(f"📄 Full response:")
            print("="*50)
            print(content)
            print("="*50)
            return True, content
        else:
            print(f"❌ FAILED - Status: {response.status_code}")
            print(f"📄 Error: {response.text[:500]}")
            return False, response.text
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        print(f"⏰ TIMEOUT after {duration:.2f}s")
        return False, "TIMEOUT"
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 ERROR after {duration:.2f}s: {type(e).__name__}: {e}")
        return False, str(e)

if __name__ == "__main__":
    print("🎯 TESTING VISION API WITH EXACT CODE PROMPT")
    print("="*60)
    
    # Test 1: JPG (handgeschriebene Lösung)
    print("\n📝 TEST 1: JPG (Handschrift)")
    jpg_success, jpg_result = test_vision_with_exact_prompt("ex_submission.jpg", "JPG")
    
    print("\n" + "="*60)
    
    # Test 2: PDF
    print("\n📄 TEST 2: PDF")
    pdf_success, pdf_result = test_vision_with_exact_prompt("ex_submission.pdf", "PDF")
    
    print("\n" + "="*60)
    print("\n🎯 SUMMARY:")
    print(f"JPG: {'✅ SUCCESS' if jpg_success else '❌ FAILED'}")
    print(f"PDF: {'✅ SUCCESS' if pdf_success else '❌ FAILED'}")
    
    if not jpg_success or not pdf_success:
        print("\n🚨 DETECTED ISSUES - CHECK OLLAMA STATUS!")