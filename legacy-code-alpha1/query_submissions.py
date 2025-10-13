#!/usr/bin/env python3
"""
Query recent submissions from Supabase database
"""
import psycopg2
import json
from datetime import datetime

# Connection details from .env file
# Supabase uses PostgreSQL, the default local port is 54322 for direct DB connection
# API URL is 54321, but we need direct DB connection

DB_CONFIG = {
    'host': 'localhost',
    'port': '54322',  # Default Supabase local DB port
    'database': 'postgres',
    'user': 'postgres',
    'password': 'postgres'  # Default local Supabase password
}

def query_recent_submissions():
    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Query the most recent 3 submissions with file_path (vision processing)
        query = """
        SELECT 
            id,
            submission_data,
            created_at,
            updated_at
        FROM submission 
        WHERE submission_data->>'file_path' IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 3;
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        print("=== RECENT SUBMISSIONS WITH VISION PROCESSING ===\n")
        
        for i, (submission_id, submission_data, created_at, updated_at) in enumerate(results, 1):
            print(f"--- SUBMISSION #{i} ---")
            print(f"Submission ID: {submission_id}")
            print(f"Created: {created_at}")
            print(f"Updated: {updated_at}")
            
            if submission_data:
                # Extract specific fields from submission_data JSON
                data = submission_data if isinstance(submission_data, dict) else json.loads(submission_data)
                
                print(f"\nExtracted Text:")
                extracted_text = data.get('extracted_text', 'N/A')
                if extracted_text and extracted_text != 'N/A':
                    # Truncate long text for readability
                    if len(str(extracted_text)) > 500:
                        print(f"  {str(extracted_text)[:500]}... [TRUNCATED]")
                    else:
                        print(f"  {extracted_text}")
                else:
                    print(f"  {extracted_text}")
                
                print(f"\nOriginal Filename: {data.get('original_filename', 'N/A')}")
                print(f"Processing Stage: {data.get('processing_stage', 'N/A')}")
                
                # Check for errors
                error_msg = data.get('error_message', data.get('error', None))
                if error_msg:
                    print(f"Error Message: {error_msg}")
                else:
                    print("Error Message: None")
                
                # Show file_path for reference
                print(f"File Path: {data.get('file_path', 'N/A')}")
                
                # Show processing status if available
                status = data.get('status', data.get('processing_status', 'N/A'))
                print(f"Status: {status}")
                
            print("\n" + "="*60 + "\n")
        
        if not results:
            print("No submissions with file_path found in the database.")
            
            # Try querying all submissions to see what's available
            cursor.execute("SELECT id, submission_data, created_at FROM submission ORDER BY created_at DESC LIMIT 3;")
            all_results = cursor.fetchall()
            
            if all_results:
                print("\n=== ALL RECENT SUBMISSIONS (without file_path filter) ===\n")
                for i, (submission_id, submission_data, created_at) in enumerate(all_results, 1):
                    print(f"--- SUBMISSION #{i} ---")
                    print(f"Submission ID: {submission_id}")
                    print(f"Created: {created_at}")
                    if submission_data:
                        data = submission_data if isinstance(submission_data, dict) else json.loads(submission_data)
                        print(f"Has file_path: {'file_path' in data}")
                        print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                    print()
            else:
                print("No submissions found in the database at all.")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        print("\nTrying alternative connection methods...")
        
        # Try with different common configurations
        alternative_configs = [
            {'host': 'localhost', 'port': '5432', 'database': 'postgres', 'user': 'postgres', 'password': 'postgres'},
            {'host': 'host.docker.internal', 'port': '54322', 'database': 'postgres', 'user': 'postgres', 'password': 'postgres'},
            {'host': '127.0.0.1', 'port': '54322', 'database': 'postgres', 'user': 'postgres', 'password': 'postgres'},
        ]
        
        for config in alternative_configs:
            try:
                print(f"Trying connection with host={config['host']}, port={config['port']}")
                conn = psycopg2.connect(**config)
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                result = cursor.fetchone()
                print(f"Success! PostgreSQL version: {result[0]}")
                cursor.close()
                conn.close()
                
                # Re-run the main query with this config
                print("\nRe-running submission query with successful connection...")
                return query_recent_submissions_with_config(config)
                
            except psycopg2.Error as e2:
                print(f"  Failed: {e2}")
                continue
    
    except Exception as e:
        print(f"Unexpected error: {e}")

def query_recent_submissions_with_config(config):
    """Re-run the query with a working configuration"""
    try:
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()
        
        # Same query as above
        query = """
        SELECT 
            id,
            submission_data,
            created_at,
            updated_at
        FROM submission 
        WHERE submission_data->>'file_path' IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 3;
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        print("=== RECENT SUBMISSIONS WITH VISION PROCESSING ===\n")
        
        for i, (submission_id, submission_data, created_at, updated_at) in enumerate(results, 1):
            print(f"--- SUBMISSION #{i} ---")
            print(f"Submission ID: {submission_id}")
            print(f"Created: {created_at}")
            print(f"Updated: {updated_at}")
            
            if submission_data:
                data = submission_data if isinstance(submission_data, dict) else json.loads(submission_data)
                
                print(f"\nExtracted Text:")
                extracted_text = data.get('extracted_text', 'N/A')
                if extracted_text and extracted_text != 'N/A':
                    if len(str(extracted_text)) > 500:
                        print(f"  {str(extracted_text)[:500]}... [TRUNCATED]")
                    else:
                        print(f"  {extracted_text}")
                else:
                    print(f"  {extracted_text}")
                
                print(f"\nOriginal Filename: {data.get('original_filename', 'N/A')}")
                print(f"Processing Stage: {data.get('processing_stage', 'N/A')}")
                
                error_msg = data.get('error_message', data.get('error', None))
                if error_msg:
                    print(f"Error Message: {error_msg}")
                else:
                    print("Error Message: None")
                
                print(f"File Path: {data.get('file_path', 'N/A')}")
                status = data.get('status', data.get('processing_status', 'N/A'))
                print(f"Status: {status}")
                
            print("\n" + "="*60 + "\n")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error with alternative config: {e}")

if __name__ == "__main__":
    query_recent_submissions()