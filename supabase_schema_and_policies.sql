-- Supabase schema and RLS policies setup script
-- =============================================

-- 1. Create 'profiles' table
CREATE TABLE public.profiles (
  id uuid NOT NULL,
  is_admin boolean NULL DEFAULT false,
  created_at timestamp with time zone NULL DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- 2. Index for 'is_admin' on 'profiles'
CREATE INDEX IF NOT EXISTS idx_profiles_is_admin ON public.profiles USING btree (is_admin) TABLESPACE pg_default;

-- 3. Create 'video_views' table
CREATE TABLE public.video_views (
  id bigserial NOT NULL,
  user_id uuid NOT NULL,
  video_id uuid NOT NULL,
  viewed_at timestamp with time zone NULL DEFAULT now(),
  CONSTRAINT video_views_pkey PRIMARY KEY (id),
  CONSTRAINT video_views_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users (id),
  CONSTRAINT video_views_video_id_fkey FOREIGN KEY (video_id) REFERENCES videos (id)
) TABLESPACE pg_default;

-- 4. Indexes for 'video_views'
CREATE INDEX IF NOT EXISTS idx_video_views_user_id ON public.video_views USING btree (user_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_video_views_video_id ON public.video_views USING btree (video_id) TABLESPACE pg_default;

-- 5. RLS Policies for 'profiles' table
-- Allow users to select their own profile
ALTER POLICY "Allow users to select their own profile"
  ON public.profiles
  TO public
  USING (
    id = auth.uid()
  );

-- Allow users to update their own profile
ALTER POLICY "Allow users to update their own profile"
  ON public.profiles
  TO public
  USING (
    id = auth.uid()
  );

-- 6. RLS Policies for 'videos' table
-- Allow users to insert their own videos (using current_setting for robust JWT support)
ALTER POLICY "Users can insert their own videos"
  ON public.videos
  TO public
  WITH CHECK (
    user_id = (current_setting('request.jwt.claim.sub', true))::uuid
  );

-- Allow users to select their own videos
ALTER POLICY "Users can select their own videos"
  ON public.videos
  TO public
  USING (
    user_id = (current_setting('request.jwt.claim.sub', true))::uuid
  );

-- Allow users to update their own videos
ALTER POLICY "Allow users to update their own videos"
  ON public.videos
  TO public
  USING (
    user_id = auth.uid()
  ); 
