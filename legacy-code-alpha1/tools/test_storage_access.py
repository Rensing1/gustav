#!/usr/bin/env python3
"""
Test script to debug section_materials storage access and 404 errors.
This script tests various scenarios to identify the root cause.
"""

import os
import sys
from supabase import create_client, Client, ClientOptions

# Add app directory to path
sys.path.append('/home/felix/gustav/app')
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

def test_storage_access():
    """Test storage access with different client configurations."""
    
    print("=== Storage Access Debug Test ===")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"Anon Key: {SUPABASE_ANON_KEY[:20]}...")
    
    # Test paths from database
    test_paths = [
        "unit_d4e43465-16f2-43b0-a226-d4ac27ba5c4b/section_0199daf7-9d82-4f3c-8085-6228eb32b0de/4fe90865-1978-4266-82b7-9898edef3e46_Politikzyklus.png",
        "unit_d4e43465-16f2-43b0-a226-d4ac27ba5c4b/section_bef2d449-68db-4530-b958-fc8c89633ac7/6d13f867-c3a4-499e-b24d-8b04d121469a_Mindestlohn1.png"
    ]
    
    teacher_id = "e0ce592a-911b-4f35-adb6-e90cd19636dd"
    student_id = "814094e1-a5df-4195-8ad1-ac634bf6ebf1"
    
    # Test 1: Service Role Client (should work)
    print("\n1. Testing with Service Role Client (should bypass RLS):")
    try:
        options = ClientOptions(postgrest_client_timeout=120, storage_client_timeout=120)
        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, options=options)
        
        for path in test_paths:
            try:
                result = service_client.storage.from_("section_materials").create_signed_url(path, 60)
                print(f"  ✅ Service role - {path[:50]}... -> {result.get('signedURL', 'No URL')[:80]}...")
            except Exception as e:
                print(f"  ❌ Service role - {path[:50]}... -> {e}")
                
    except Exception as e:
        print(f"  ❌ Service role client creation failed: {e}")
    
    # Test 2: Anonymous Client (should fail due to RLS)
    print("\n2. Testing with Anonymous Client (should fail due to RLS):")
    try:
        options = ClientOptions(postgrest_client_timeout=120, storage_client_timeout=120)
        anon_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)
        
        for path in test_paths:
            try:
                result = anon_client.storage.from_("section_materials").create_signed_url(path, 60)
                print(f"  ✅ Anonymous - {path[:50]}... -> {result.get('signedURL', 'No URL')[:80]}...")
            except Exception as e:
                print(f"  ❌ Anonymous - {path[:50]}... -> {e}")
                
    except Exception as e:
        print(f"  ❌ Anonymous client creation failed: {e}")
    
    # Test 3: Simulate teacher token (manual auth simulation)
    print("\n3. Testing with Teacher Token Simulation:")
    try:
        # This is a simplified test - in reality we need actual JWT
        options = ClientOptions(postgrest_client_timeout=120, storage_client_timeout=120)
        teacher_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)
        
        # Note: This won't work without actual JWT, but let's see the error
        for path in test_paths:
            try:
                result = teacher_client.storage.from_("section_materials").create_signed_url(path, 60)
                print(f"  ✅ Teacher sim - {path[:50]}... -> {result.get('signedURL', 'No URL')[:80]}...")
            except Exception as e:
                print(f"  ❌ Teacher sim - {path[:50]}... -> {e}")
                
    except Exception as e:
        print(f"  ❌ Teacher simulation failed: {e}")
    
    # Test 4: Check what happens with non-existent file
    print("\n4. Testing with non-existent file:")
    try:
        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        fake_path = "unit_fake-uuid/section_fake-uuid/fake_file.png"
        
        try:
            result = service_client.storage.from_("section_materials").create_signed_url(fake_path, 60)
            print(f"  ✅ Non-existent file -> {result.get('signedURL', 'No URL')[:80]}...")
        except Exception as e:
            print(f"  ❌ Non-existent file -> {e}")
            
    except Exception as e:
        print(f"  ❌ Non-existent file test failed: {e}")

if __name__ == "__main__":
    test_storage_access()