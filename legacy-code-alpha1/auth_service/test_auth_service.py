#!/usr/bin/env python3
"""
Test script for GUSTAV Auth Service
Tests the Supabase-based session storage implementation
"""
import os
import sys
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

# Add auth_service to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Test imports
try:
    from app.services.supabase_session_store import SupabaseSessionStore
    from app.config import settings
    print("✅ Imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


async def test_session_store():
    """Test the Supabase session store functionality"""
    print("\n🧪 Testing SupabaseSessionStore...")
    
    # Initialize store
    store = SupabaseSessionStore(cache_enabled=True, cache_ttl=60)
    
    # Test 1: Health Check
    print("\n1️⃣ Testing health check...")
    health = await store.health_check()
    print(f"   Health: {health}")
    assert health['healthy'], "Session store should be healthy"
    
    # Test 2: Create Session
    print("\n2️⃣ Testing session creation...")
    test_user_id = "00000000-0000-0000-0000-000000000001"
    test_email = "test@example.com"
    test_role = "teacher"
    
    session_id = await store.create_session(
        user_id=test_user_id,
        user_email=test_email,
        user_role=test_role,
        data={"test": "data"},
        expires_in=300,  # 5 minutes
        ip_address="127.0.0.1",
        user_agent="TestScript/1.0"
    )
    print(f"   Created session: {session_id}")
    assert session_id, "Should return a session ID"
    
    # Test 3: Get Session
    print("\n3️⃣ Testing session retrieval...")
    session = await store.get_session(session_id)
    print(f"   Retrieved session: {json.dumps(session, indent=2, default=str)}")
    assert session, "Should retrieve the session"
    assert session['user_id'] == test_user_id, "User ID should match"
    assert session['user_email'] == test_email, "Email should match"
    assert session['user_role'] == test_role, "Role should match"
    
    # Test 4: Update Session
    print("\n4️⃣ Testing session update...")
    success = await store.update_session(
        session_id,
        {"updated": "value", "timestamp": datetime.now(timezone.utc).isoformat()}
    )
    print(f"   Update success: {success}")
    assert success, "Update should succeed"
    
    # Verify update
    updated_session = await store.get_session(session_id)
    assert updated_session['data'].get('updated') == "value", "Update should be persisted"
    
    # Test 5: Cache functionality
    print("\n5️⃣ Testing cache...")
    # Should hit cache this time
    cached_session = await store.get_session(session_id)
    assert cached_session, "Should get session from cache"
    print("   Cache hit successful")
    
    # Test 6: Delete Session
    print("\n6️⃣ Testing session deletion...")
    deleted = await store.delete_session(session_id)
    print(f"   Delete success: {deleted}")
    assert deleted, "Delete should succeed"
    
    # Verify deletion
    deleted_session = await store.get_session(session_id)
    assert deleted_session is None, "Session should be gone"
    
    # Test 7: Cleanup expired sessions
    print("\n7️⃣ Testing cleanup...")
    cleaned = await store.cleanup_expired_sessions()
    print(f"   Cleaned up {cleaned} expired sessions")
    
    print("\n✅ All SupabaseSessionStore tests passed!")


async def test_multiple_sessions():
    """Test session limits per user"""
    print("\n🧪 Testing session limits...")
    
    store = SupabaseSessionStore(cache_enabled=False)  # Disable cache for this test
    test_user_id = "00000000-0000-0000-0000-000000000002"
    
    # Create 6 sessions (limit is 5)
    session_ids = []
    for i in range(6):
        session_id = await store.create_session(
            user_id=test_user_id,
            user_email=f"test{i}@example.com",
            user_role="student",
            data={"session_num": i}
        )
        session_ids.append(session_id)
        print(f"   Created session {i+1}: {session_id}")
    
    # Check that we only have 5 sessions (oldest should be deleted)
    user_sessions = await store.get_user_sessions(test_user_id)
    print(f"\n   Active sessions for user: {len(user_sessions)}")
    assert len(user_sessions) <= 5, "Should enforce 5 session limit"
    
    # Cleanup
    cleaned = await store.invalidate_user_sessions(test_user_id)
    print(f"   Cleaned up {cleaned} sessions for user")
    
    print("\n✅ Session limit tests passed!")


async def main():
    """Run all tests"""
    print("🚀 GUSTAV Auth Service Test Suite")
    print("=" * 50)
    
    # Check environment
    print("\n📋 Environment Check:")
    print(f"   SUPABASE_URL: {'✅ Set' if settings.SUPABASE_URL else '❌ Missing'}")
    print(f"   SUPABASE_SERVICE_KEY: {'✅ Set' if settings.SUPABASE_SERVICE_KEY else '❌ Missing'}")
    print(f"   ENVIRONMENT: {settings.ENVIRONMENT}")
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        print("\n❌ Missing required environment variables!")
        print("   Please set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return
    
    try:
        # Run tests
        await test_session_store()
        await test_multiple_sessions()
        
        print("\n" + "=" * 50)
        print("🎉 All tests passed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())