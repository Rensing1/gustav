#!/usr/bin/env python3
"""
Feedback Worker - Asynchroner Prozessor für KI-Feedback-Generierung

Dieser Worker läuft als separater Prozess und arbeitet die Feedback-Queue ab.
Er verarbeitet sowohl reguläre Aufgaben als auch Mastery-Aufgaben.
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import traceback

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Import worker-specific modules
from workers.worker_ai import process_regular_feedback, process_mastery_feedback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('feedback_worker.log')
    ]
)
logger = logging.getLogger(__name__)

class FeedbackWorker:
    """Worker class for processing feedback generation queue"""
    
    def __init__(self):
        self.running = True
        self.supabase: Optional[Client] = None
        self.processed_count = 0
        self.max_processed_before_restart = 1000  # Restart after 1000 jobs to prevent memory leaks
        self.polling_interval = 5  # seconds
        self.health_check_interval = 60  # seconds
        self.last_health_check = datetime.now()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        
    def handle_shutdown(self, signum, frame):
        """Graceful shutdown handler"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        
    def connect_to_supabase(self) -> bool:
        """Establish connection to Supabase using environment variables directly"""
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            
            if not supabase_url or not supabase_key:
                logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
                logger.error(f"SUPABASE_URL: {'✓' if supabase_url else '✗'}")
                logger.error(f"SUPABASE_SERVICE_ROLE_KEY: {'✓' if supabase_key else '✗'}")
                return False
                
            self.supabase = create_client(supabase_url, supabase_key)
            logger.info(f"Successfully connected to Supabase at {supabase_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
            
    def get_next_submission(self) -> Optional[Dict[str, Any]]:
        """Get next submission from queue using database function"""
        try:
            result = self.supabase.rpc('get_next_feedback_submission').execute()
            
            if result.data and len(result.data) > 0:
                submission = result.data[0]
                logger.info(f"Retrieved submission {submission['id']} from queue (retry_count: {submission['retry_count']})")
                return submission
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next submission: {e}")
            return None
            
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task information to determine if it's a mastery task"""
        try:
            # Phase 4: Use views instead of old task table
            # First try regular tasks
            result = self.supabase.table('all_regular_tasks').select('is_mastery').eq('id', task_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            # If not found, try mastery tasks  
            result = self.supabase.table('all_mastery_tasks').select('is_mastery').eq('id', task_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            
            logger.warning(f"Task {task_id} not found in either view")
            return None
        except Exception as e:
            logger.error(f"Error getting task info for {task_id}: {e}")
            return None
            
    def process_submission(self, submission: Dict[str, Any]) -> bool:
        """Process a single submission (regular, mastery, or file upload)"""
        submission_id = submission['id']
        task_id = submission['task_id']
        student_id = submission['student_id']
        
        try:
            # Determine if this is a mastery task
            task_info = self.get_task_info(task_id)
            if not task_info:
                raise Exception(f"Could not retrieve task info for task {task_id}")
                
            is_mastery = task_info.get('is_mastery', False)
            
            logger.info(f"Starting {'mastery' if is_mastery else 'regular'} feedback generation for submission {submission_id}")
            start_time = time.time()
            
            if is_mastery:
                # Process mastery submission using worker-specific function
                success = process_mastery_feedback(
                    supabase=self.supabase,
                    submission_id=submission_id,
                    submission_data=submission.get('submission_data', {}),
                    task_id=task_id,
                    student_id=student_id
                )
                
                if not success:
                    raise Exception("Mastery processing failed")
                
            else:
                # Process regular submission using worker-specific function
                success = process_regular_feedback(
                    supabase=self.supabase,
                    submission_id=submission_id
                )
                
                if not success:
                    raise Exception("Regular feedback processing failed")
            
            processing_time = time.time() - start_time
            logger.info(f"Successfully generated {'mastery' if is_mastery else 'regular'} feedback for submission {submission_id} in {processing_time:.2f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing submission {submission_id}: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Mark as failed/retry
            try:
                error_message = f"Fehler bei Feedback-Generierung: {str(e)}"
                
                self.supabase.rpc('mark_feedback_failed', {
                    'p_submission_id': submission_id,
                    'p_error_message': error_message
                }).execute()
            except Exception as update_error:
                logger.error(f"Failed to update submission status: {update_error}")
                
            return False
    
            
    def reset_stuck_jobs(self):
        """Reset jobs that have been processing for too long"""
        try:
            result = self.supabase.rpc('reset_stuck_feedback_jobs').execute()
            
            if result.data and result.data > 0:
                logger.info(f"Reset {result.data} stuck jobs")
                
        except Exception as e:
            logger.error(f"Error resetting stuck jobs: {e}")
            
    def health_check(self):
        """Perform periodic health checks"""
        now = datetime.now()
        
        if (now - self.last_health_check).seconds >= self.health_check_interval:
            self.last_health_check = now
            
            # Reset stuck jobs
            self.reset_stuck_jobs()
            
            # Log worker status
            logger.info(f"Health check: Processed {self.processed_count} submissions")
            
            # Check if we should restart to prevent memory leaks
            if self.processed_count >= self.max_processed_before_restart:
                logger.info("Reached max processed count, initiating graceful restart...")
                self.running = False
                
    def run(self):
        """Main worker loop"""
        logger.info("Starting Feedback Worker...")
        
        # Connect to Supabase
        if not self.connect_to_supabase():
            logger.error("Failed to connect to Supabase, exiting...")
            return
            
        logger.info(f"Worker started, polling every {self.polling_interval} seconds")
        
        while self.running:
            try:
                # Perform health check
                self.health_check()
                
                # Get next submission from queue
                submission = self.get_next_submission()
                
                if submission:
                    # Process the submission
                    success = self.process_submission(submission)
                    
                    if success:
                        self.processed_count += 1
                        
                    # Small delay to prevent tight loops on errors
                    time.sleep(0.5)
                else:
                    # No submissions in queue, wait before polling again
                    time.sleep(self.polling_interval)
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
                
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                time.sleep(self.polling_interval)
                
        logger.info(f"Worker stopped after processing {self.processed_count} submissions")


def main():
    """Main entry point"""
    worker = FeedbackWorker()
    
    try:
        worker.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
        
    sys.exit(0)


if __name__ == "__main__":
    main()