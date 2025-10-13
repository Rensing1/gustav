-- Create submissions bucket for student file uploads
-- This bucket stores uploaded images and PDFs from student solutions

-- 1. Create bucket (only if it doesn't exist)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'submissions',
    'submissions',
    false, -- Not public - authenticated users only
    10485760, -- 10MB Limit
    ARRAY['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'] -- Only specific file types
) ON CONFLICT (id) DO NOTHING; -- Don't fail if bucket already exists