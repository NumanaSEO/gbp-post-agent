import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests
from bs4 import BeautifulSoup
import io
import datetime
import re # NEW: For extracting ID from URL

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Agency Post Factory", page_icon="🏥", layout="wide")

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button {width: 100%; border-radius: 5px; height: 3em; font-weight: bold;} 
    div[data-testid="stStatusWidget"] {border: 1px solid #ddd; border-radius: 10px; padding: 10px;}
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR: AUTH & CONFIG ---
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # 1. AUTHENTICATION
    st.subheader("1. System Status")
    auth_ready = False
    creds = None 
    robot_email = "Unknown"
    
    if "gcp_service_account" in st.secrets:
        try:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/drive"]
            )
            project_id = st.secrets["gcp_service_account"]["project_id"]
            robot_email = st.secrets["gcp_service_account"]["client_email"]
            
            vertexai.init(project=project_id, location="us-central1", credentials=creds)
            auth_ready = True
            st.success(f"✅ AI System Online")
        except Exception as e:
            st.error(f"Secrets Error: {e}")
    else:
        st.warning("⚠️ No Secrets found.")

    # 2. PERMISSIONS
    if auth_ready:
        st.divider()
        st.subheader("📂 Folder Permissions")
        st.info("Share your Drive Folder with:")
        st.code(robot_email, language=None)

    # 3. SETTINGS
    st.divider()
    selected_model_name = st.selectbox("Text Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-001"], index=0)
    temperature = st.slider("Creativity", 0.0, 1.0, 0.2)
    
    st.divider()
    st.info("VA Checklist: \n1. Safe Image? \n2. No Fluff? \n3. Keyword included?")

# --- FUNCTIONS ---

def extract_folder_id(input_string):
    """Extracts ID from a full URL or returns the ID if pasted directly."""
    if not input_string: return None
    
    # Logic: Look for the part after /folders/
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', input_string)
    if match:
        return match.group(1)
    
    # If no URL pattern found, assume the user pasted the ID directly
    return input_string.strip()

def get_website_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = " ".join([p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])])
        return text[:5000].strip()
    except: return None

def generate_post_content(text, focus_topic, keyword, model_name, temp):
    model = GenerativeModel(model_name)
    keyword_instruction = f"MANDATORY: Include '{keyword}'." if keyword else ""
    prompt = f"""
    You are a Front Desk Receptionist. Write a Google Business Profile update.
    CONTEXT: {text} | FOCUS: {focus_topic} | KEYWORD: {keyword}
    GUIDELINES: No fluff ("Unleash", "Elevate"). Grade 8 English. Factual. {keyword_instruction}
    IMAGE SAFETY: If topic involves CHILDREN/PATIENTS, prompt for a ROOM/OBJECT photo. NO PEOPLE.
    OUTPUT FORMAT:
    HEADLINE: [Header]
    BODY: [Body]
    IMAGE_PROMPT: [Prompt]
    """
    response = model.generate_content(prompt, generation_config={"temperature": temp})
    return response.text

def generate_image(prompt):
    try:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        images = model.generate_images(prompt=prompt+", photorealistic, 4k, no text", number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
        return images[0]
    except:
        try:
            model = ImageGenerationModel.from_pretrained("imagegeneration@006")
            images = model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
            return images[0]
        except: return None

def upload_to_drive(creds, folder_id, filename, file_path, mime_type):
    try:
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaFileUpload(file_path, mimetype=mime_type)
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id, webViewLink', supportsAllDrives=True
        ).execute()
        return {"success": True, "link": file.get('webViewLink')}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- MAIN UI ---

st.title("🏥 SEO Post Factory")
st.markdown("Generate content and **save directly to the client folder**.")
st.divider()

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Input Details")
    url_input = st.text_input("Service Page URL")
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1: keyword_input = st.text_input("Keyword")
    with sub_col2: focus_input = st.text_input("Focus/Offer")
    
    st.divider()
    
    st.subheader("2. Where to Save?")
    # UPDATED INPUT LABEL
    folder_input_raw = st.text_input(
        "Google Drive Folder URL (or ID)", 
        placeholder="Paste the full link: https://drive.google.com/drive/folders/...",
        help="You can paste the full URL from your browser bar."
    )
    
    # CLEAN THE ID
    folder_id_clean = extract_folder_id(folder_input_raw)
    
    if folder_id_clean:
        st.caption(f"✅ Detected Folder ID: `{folder_id_clean}`")
    else:
        st.info("ℹ️ Leave blank to generate without saving.")

    st.write("") 
    run_btn = st.button("✨ Generate Post", type="primary")

    if run_btn:
        if not auth_ready: st.error("Check Sidebar Auth"); st.stop()
        if not url_input: st.warning("Please enter a URL"); st.stop()
        
        with st.status("Agent is working...", expanded=True) as status:
            # 1. Scrape
            st.write("🕷️ Reading site...")
            site_text = get_website_text(url_input)
            if not site_text: st.error("Scrape failed."); st.stop()
            
            # 2. Text
            st.write("🧠 Writing content...")
            try:
                raw_output = generate_post_content(site_text, focus_input, keyword_input, selected_model_name, temperature)
                headline = raw_output.split("HEADLINE:")[1].split("BODY:")[0].strip()
                body = raw_output.split("BODY:")[1].split("IMAGE_PROMPT:")[0].strip()
                img_prompt = raw_output.split("IMAGE_PROMPT:")[1].strip()
            except: 
                headline = "Error Parsing"; body = raw_output; img_prompt = "Error"

            # 3. Image
            st.write("📸 Generating image...")
            generated_image = generate_image(img_prompt)
            
            # 4. Save Logic
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            base_name = f"Post_{timestamp}"
            local_img_name = "temp_image.jpg"
            img_result = {"success": False}
            doc_result = {"success": False}
            
            if generated_image:
                generated_image.save(local_img_name, include_generation_parameters=False)
                if folder_id_clean:
                    st.write("☁️ Uploading Image...")
                    img_result = upload_to_drive(creds, folder_id_clean, f"{base_name}.jpg", local_img_name, "image/jpeg")

            if folder_id_clean:
                st.write("☁️ Uploading Text...")
                text_content = f"HEADLINE: {headline}\n\nBODY: {body}\n\nPROMPT: {img_prompt}\n\nSOURCE: {url_input}"
                with open("temp_text.txt", "w") as f: f.write(text_content)
                doc_result = upload_to_drive(creds, folder_id_clean, f"{base_name}.txt", "temp_text.txt", "text/plain")
            
            status.update(label="Complete!", state="complete", expanded=False)

            # --- RESULT DISPLAY ---
            with col2:
                st.subheader("3. Final Result")
                if generated_image: st.image(local_img_name)
                else: st.warning("Image Blocked (Safety Filter)")

                if folder_id_clean:
                    if img_result["success"] or doc_result["success"]:
                        st.success(f"✅ Saved to Drive!")
                        if img_result.get("link"): st.markdown(f"[📂 Open Image]({img_result['link']})")
                        if doc_result.get("link"): st.markdown(f"[📄 Open Text]({doc_result['link']})")
                    if not img_result["success"] and generated_image:
                        st.error(f"Image Upload Failed: {img_result.get('error')}")
                    if not doc_result["success"]:
                        st.error(f"Text Upload Failed: {doc_result.get('error')}")
                
                st.divider()
                st.text_input("Headline", headline)
                st.text_area("Body", body)
