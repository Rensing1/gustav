#!/bin/bash
# Run tests for auth service

echo "Running Auth Service Tests..."

# Run unit tests
echo "=== Unit Tests ==="
pytest tests/test_secure_session_store.py -v

# Run route tests  
echo -e "\n=== Route Tests ==="
pytest tests/test_auth_routes.py -v

# Run all tests with coverage
echo -e "\n=== All Tests with Coverage ==="
pytest --cov=app --cov-report=term-missing

# Run specific test markers
echo -e "\n=== Quick Unit Tests Only ==="
pytest -m "not slow" -v