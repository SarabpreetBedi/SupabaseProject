# pip install streamlit supabase pandas

import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import pandas as pd
import time
import requests
import json
import httpx

# 🔐 Supabase credentials from secrets.toml
SUPABASE_URL = st.secrets["SUPABASE_URL"]
service_role_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
if not service_role_key:
    st.error("SUPABASE_SERVICE_ROLE_KEY is missing from your secrets! Please add it to .streamlit/secrets.toml or Streamlit Cloud secrets.")
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is missing from your secrets!")
SUPABASE_KEY = service_role_key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

#  Session state
if 'user' not in st.session_state:
    st.session_state.user = None
if 'profile' not in st.session_state:
    st.session_state.profile = {}

# ✅ Admin check (safe)
def is_admin(user_id):
    try:
        res = supabase.table("profiles").select("is_admin").eq("id", user_id).execute()
        if res.data:
            return res.data[0].get("is_admin", False)
        return False
    except Exception:
        return False

# 🔐 Login logic
def login():
    st.subheader("Login")
    email = st.text_input("Email", key="login_email")
    pwd = st.text_input("Password", type="password", key="login_pwd")
    if st.button("Login"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
            if res.user:
                st.session_state.user = res.user
                st.session_state.session = res.session  # Store session for JWT access
                # Do NOT re-create the supabase client here!
                # Try to get existing profile, create one if it doesn't exist
                try:
                    profile_result = supabase.table("profiles").select("is_admin").eq("id", res.user.id).execute()
                    if profile_result.data:
                        st.session_state.profile = profile_result.data[0]
                    else:
                        # Create profile if it doesn't exist
                        profile_data = {"id": res.user.id, "is_admin": False}
                        supabase.table("profiles").insert(profile_data).execute()
                        st.session_state.profile = profile_data
                        st.info("📝 Profile created for new user")
                except Exception as profile_error:
                    st.warning("⚠️ Could not load profile, creating new one...")
                    try:
                        profile_data = {"id": res.user.id, "is_admin": False}
                        supabase.table("profiles").insert(profile_data).execute()
                        st.session_state.profile = profile_data
                    except Exception as create_error:
                        st.error(f"❌ Could not create profile: {create_error}")
                        st.session_state.profile = {"is_admin": False}
                st.success("✅ Logged in")
                
            else:
                st.error("❌ Login failed")
        except Exception as e:
            st.error(f"❌ Login error: {e}")

# 📝 Sign up logic
def signup():
    st.subheader("Create Account")
    email = st.text_input("Email", key="su_email")
    pwd = st.text_input("Password", type="password", key="su_pwd")
    if st.button("Sign Up"):
        try:
            res = supabase.auth.sign_up({"email": email, "password": pwd})
            if res.user:
                import time
                time.sleep(1)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        profile_data = {"id": res.user.id, "is_admin": False}
                        supabase.table("profiles").insert(profile_data).execute()
                        st.success("✅ Account created successfully!")
                        st.info("📧 Please check your email and confirm your account before logging in.")
                        break
                    except Exception as profile_error:
                        if attempt < max_retries - 1:
                            st.info(f"⏳ Waiting for user account to be ready... (attempt {attempt + 1}/{max_retries})")
                            time.sleep(2)
                            continue
                        else:
                            st.warning("⚠️ Account created but profile setup failed.")
                            st.error(f"Profile error: {profile_error}")
                            st.info("🔧 To fix this issue:")
                            st.markdown("""
                            1. Go to your Supabase Dashboard
                            2. Navigate to SQL Editor
                            3. Run this SQL command:
                            ```sql
                            DROP TABLE IF EXISTS public.profiles CASCADE;
                            CREATE TABLE public.profiles (
                              id uuid PRIMARY KEY,
                              is_admin boolean DEFAULT false,
                              created_at timestamp with time zone DEFAULT now()
                            );
                            ALTER TABLE public.profiles DISABLE ROW LEVEL SECURITY;
                            ```
                            4. Try signing up again
                            """)
                            st.info("📧 Please check your email and confirm your account before logging in.")
                            break
            else:
                st.error("❌ Sign-up error")
        except Exception as e:
            st.error(f"❌ Sign-up error: {e}")

# 🔒 Logout
def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.profile = {}
    st.success("Logged out")

def insert_video_with_jwt(user, file, url, title, desc, tags, cat, project_url):
    # Get the service role key, or show a clear error if missing
    service_role_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
    if not service_role_key:
        st.error("SUPABASE_SERVICE_ROLE_KEY is missing from your secrets! Please add it to .streamlit/secrets.toml or Streamlit Cloud secrets.")
        return None
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json"
    }
    data = {
        "user_id": user.id,
        "file_name": file.name,
        "url": url,
        "title": title,
        "description": desc,
        "tags": tags,
        "category": cat
    }
    with httpx.Client() as client:
        response = client.post(f"{project_url}/rest/v1/videos", headers=headers, json=data)
    return response

# 📤 Upload videos
def upload_video():
    st.subheader("Upload a New Video")
    st.info("📁 Supported formats: MP4, MOV, AVI | Max size: 100MB")
    # Ensure both user and session exist before proceeding
    if not st.session_state.get("user") or not st.session_state.get("session"):
        st.error("Session or user not found. Please log out and log in again.")
        return
    # Debug: print JWT and session (remove after testing)
    jwt = st.session_state.session.access_token
    st.write("JWT (copy this for jwt.io):")
    st.code(jwt)
    # Also print the user_id and sub for comparison
    try:
        import jwt as pyjwt
        payload = pyjwt.decode(jwt, options={"verify_signature": False})
        st.write("JWT sub:", payload.get("sub"))
        st.write("Session user_id:", st.session_state.user.id)
    except Exception as e:
        st.write("JWT decode error:", e)
    st.write("Session:", st.session_state.session)
    file = st.file_uploader("Select video", type=["mp4", "mov", "avi"])
    title = st.text_input("Title")
    desc = st.text_area("Description")
    tags_in = st.text_input("Tags (comma-separated)")
    cat = st.selectbox("Category", ["Education", "Entertainment", "Tutorial", "Other"])
    if file and st.button("Upload"):
        user_id = st.session_state.user.id
        fname = f"{user_id}/{file.name}"
        file_size_mb = len(file.read()) / (1024*1024)
        file.seek(0)
        if file_size_mb > 100:
            st.error(f"❌ File too large: {file_size_mb:.2f} MB (max 100MB)")
            st.info("💡 Please compress your video or choose a smaller file")
            return
        try:
            with st.spinner("🔄 Uploading video... This may take a few minutes for large files."):
                file_bytes = file.read()
                file.seek(0)
                # Upload to Supabase storage
                result = supabase.storage.from_("videos").upload(
                    fname,
                    file_bytes,
                    {"content-type": file.type}
                )
                url = supabase.storage.from_("videos").get_public_url(fname)
                tags = [t.strip() for t in tags_in.split(",") if t.strip()]
                # Insert into videos table using REST API and JWT
                response = insert_video_with_jwt(
                    user=st.session_state.user,
                    file=file,
                    url=url,
                    title=title,
                    desc=desc,
                    tags=tags,
                    cat=cat,
                    project_url=st.secrets["SUPABASE_URL"]
                )
                if response: # Check if response is not None (meaning no error)
                    st.write("Insert result:", response.json())
                    if response.status_code == 201:
                        st.success("🎉 Video uploaded and record inserted!")
                    else:
                        st.error(f"Insert failed: {response.json()}")
                else:
                    st.error("❌ Failed to insert video record due to missing service role key.")
        except Exception as e:
            st.error(f"❌ Upload failed: {e}")
            if "timeout" in str(e).lower():
                st.error("⏰ Upload timed out. Try a smaller file or check your internet connection.")
                st.info("💡 Tips:")
                st.info("• Compress your video to reduce file size")
                st.info("• Use a shorter video (under 5 minutes)")
                st.info("• Try uploading during off-peak hours")
            else:
                st.info("💡 Make sure your video file is not too large (max 100MB)")
                st.info("💡 Try compressing your video or using a smaller file")

# 🎥 View and search videos
def view_videos(admin=False):
    st.subheader("Your Videos" if not admin else "All Videos")
    sidebar = st.sidebar

    # Check if user is logged in
    if not st.session_state.user:
        st.info("Please log in to view your videos.")
        return

    try:
        if admin:
            res = supabase.table("videos").select("*").order("created_at", desc=True).execute()
        else:
            res = supabase.table("videos").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute()
        vids = res.data if hasattr(res, "data") else None
    except Exception as e:
        st.error(f"Error loading videos: {e}")
        return

    if not vids:
        st.info("No videos uploaded yet.")
        return

    cats = list({v["category"] for v in vids if v.get("category")})
    fcat = sidebar.multiselect("Filter by category", cats)
    ftag = sidebar.text_input("Filter by tags (comma-separated)")
    fsearch = sidebar.text_input("Search title/description")
    df = pd.DataFrame(vids)
    if fcat:
        df = df[df.category.isin(fcat)]
    if ftag:
        tags = [t.strip() for t in ftag.split(",") if t.strip()]
        df = df[df.tags.apply(lambda tx: tx and all(t in tx for t in tags))]
    if fsearch:
        df = df[df.title.str.contains(fsearch, case=False, na=False) | df.description.str.contains(fsearch, case=False, na=False)]
    for _, v in df.iterrows():
        try:
            video_url = v.url if isinstance(v.url, str) else v.url.public_url if hasattr(v.url, 'public_url') else str(v.url)
            st.video(video_url, start_time=0)
            st.markdown(f"**{v.title}** ({v.category})")
            st.write(v.description)
            st.write(", ".join(v.tags or []))
            play_placeholder = st.empty()
            if play_placeholder.button("Play", key=f"play_{v.id}"):
                supabase.table("video_views").insert({"user_id": st.session_state.user.id, "video_id": v.id}).execute()
                info_placeholder = st.empty()
                info_placeholder.info("Click the play button on the video above to watch.")
                time.sleep(3)
                info_placeholder.empty()
            st.write("---")
        except Exception as e:
            st.error(f"Error displaying video {v.title}: {e}")
            st.write("---")

# 📊 Admin analytics dashboard
def view_dashboard():
    st.subheader("Admin Dashboard")
    try:
        views = supabase.table("video_views").select("video_id, count(*) as plays").group("video_id").execute().data
        dfv = pd.DataFrame(views)
        vids = supabase.table("videos").select("id, title").execute().data
        dft = pd.DataFrame(vids)
        report = dfv.merge(dft, left_on="video_id", right_on="id")
        report = report[["title", "plays"]].sort_values("plays", ascending=False)
        st.bar_chart(report.set_index("title"))
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")

# 🚀 App UI flow
st.title("🎥 Video Upload & Manager")

if st.session_state.user:
    st.sidebar.write(f"Logged in as: `{st.session_state.user.email}`")
    if st.sidebar.button("Logout"):
        logout()
    is_admin_user = st.session_state.profile.get("is_admin", False)
    upload_video()
    view_videos(admin=is_admin_user)
    if is_admin_user:
        view_dashboard()
else:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        login()
    with tab2:
        signup()








