#!/usr/bin/env python3
"""
Direct Ollama Vision API Test
Testet die Vision-API außerhalb des Worker-Contexts
"""
import requests
import base64
import time
import json

def test_ollama_vision():
    """Test der direkten Ollama Vision-API"""
    
    # Simple test image (1x1 pixel white PNG)
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    
    ollama_url = "http://localhost:11434"
    
    print(f"🧪 Testing Ollama Vision API at {ollama_url}")
    print(f"📊 Model: gemma3:12b")
    print(f"🖼️  Test image: 1x1 white pixel PNG")
    
    start_time = time.time()
    
    try:
        # Test /api/chat endpoint
        print("\n📡 Testing /api/chat endpoint...")
        response = requests.post(f"{ollama_url}/api/chat", json={
            "model": "gemma3:12b",
            "messages": [{
                "role": "user", 
                "content": "What do you see in this image? Be very brief.",
                "images": [test_image_b64]
            }],
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }, timeout=30)
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("message", {}).get("content", "")
            print(f"✅ SUCCESS - Chat API responded in {duration:.2f}s")
            print(f"📝 Response: {content}")
            return True
        else:
            print(f"❌ FAILED - Status: {response.status_code}")
            print(f"📄 Error: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        print(f"⏰ TIMEOUT after {duration:.2f}s")
        return False
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 ERROR after {duration:.2f}s: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_ollama_vision()
    exit(0 if success else 1)