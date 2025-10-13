#!/usr/bin/env python3
"""
Test Redis connection independently
"""
import redis
import asyncio
import redis.asyncio as async_redis

print("Testing Redis connection...")

# Test 1: Sync connection
try:
    sync_client = redis.Redis(host='redis', port=6379, decode_responses=True)
    sync_result = sync_client.ping()
    print(f"✓ Sync Redis connection: {sync_result}")
except Exception as e:
    print(f"✗ Sync Redis failed: {e}")

# Test 2: Async connection without pool
async def test_async():
    try:
        client = async_redis.Redis(host='redis', port=6379, decode_responses=True)
        result = await client.ping()
        print(f"✓ Async Redis connection: {result}")
        await client.close()
    except Exception as e:
        print(f"✗ Async Redis failed: {e}")

# Test 3: Async with URL
async def test_async_url():
    try:
        client = async_redis.from_url("redis://redis:6379", decode_responses=True)
        result = await client.ping()
        print(f"✓ Async Redis URL connection: {result}")
        await client.close()
    except Exception as e:
        print(f"✗ Async Redis URL failed: {e}")

# Run async tests
asyncio.run(test_async())
asyncio.run(test_async_url())