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
            # Load Creds with Drive Scope
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/drive"]
            )
            project_id = st.secrets["gcp_service_account"]["project_id"]
            robot_email = st.secrets["gcp_service_account"]["client_email"]
            
            vertexai.init(project=project_id, location="us-central1", credentials=creds)
            auth_ready = True
            st.success(f"✅ AI System Online")
            st.caption(f"Project: {project_id}")
        except Exception as e:
            st.error(f"Secrets Error: {e}")
    else:
        st.warning("⚠️ No Secrets found.")

    # 2. ROBOT EMAIL (For Sharing)
    if auth_ready:
        st.divider()
        st.subheader("📂 Folder Permissions")
        st.info("You must 'Share' your Google Drive folder with this email address:")
        st.code(robot_email, language=None)
        st.caption("Copy this email -> Go to Drive -> Right Click Folder -> Share -> Paste.")

    # 3. AI SETTINGS
    st.divider()
    st.subheader("🧠 Model Settings")
    selected_model_name = st.selectbox(
        "Text Model", 
        ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-001"], 
        index=0
    )
    temperature = st.slider("Creativity", 0.0, 1.0, 0.2)

# --- FUNCTIONS ---

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
    
    *** IMAGE SAFETY ***: If topic involves CHILDREN/PATIENTS, prompt for a ROOM/OBJECT photo. NO PEOPLE.

    OUTPUT FORMAT:
    HEADLINE: [Header]
    BODY: [Body]
    IMAGE_PROMPT: [Prompt]
    """
    response = model.generate_content(prompt, generation_config={"temperature": temp})
    return response.text

def generate_image(prompt):
    # Try Imagen 3 first
    try:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        images = model.generate_images(prompt=prompt+", photorealistic, 4k, no text", number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
        return images[0]
    except:
        # Fallback to Imagen 2 if 3 fails
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
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return file.get('webViewLink')
    except Exception as e:
        print(f"Drive Upload Error: {e}")
        return None

# --- MAIN UI ---

st.title("🏥 SEO Post Factory")
st.markdown("Generate content and **save directly to the client folder**.")
st.divider()

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Input Details")
    url_input = st.text_input("Service Page URL", placeholder="https://client.com/service")
    
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1: keyword_input = st.text_input("Target Keyword", placeholder="e.g. Dentist 78704")
    with sub_col2: focus_input = st.text_input("Focus/Offer", placeholder="e.g. Summer Special")
    
    st.divider()
    
    st.subheader("2. Where to Save?")
    folder_id_input = st.text_input(
        "Google Drive Folder ID", 
        placeholder="e.g. 1A2b3C4d...",
        help="Copy the ID from the end of the Google Drive URL."
    )
    
    if not folder_id_input:
        st.info("ℹ️ Leave blank to generate without saving to Drive.")

    st.write("") # Spacer
    run_btn = st.button("✨ Generate Post", type="primary")

    if run_btn:
        if not auth_ready: st.error("Check Sidebar Auth"); st.stop()
        if not url_input: st.warning("Please enter a URL"); st.stop()
        
        with st.status("Agent is working...", expanded=True) as status:
            # 1. Scrape
            st.write("🕷️ Reading website...")
            site_text = get_website_text(url_input)
            if not site_text: st.error("Scrape failed. Check URL."); st.stop()
            
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
            img_link = None
            doc_link = None
            
            if generated_image:
                generated_image.save(local_img_name, include_generation_parameters=False)
                # Upload Image
                if folder_id_input:
                    st.write("☁️ Uploading Image to Drive...")
                    img_link = upload_to_drive(creds, folder_id_input, f"{base_name}.jpg", local_img_name, "image/jpeg")

            # Upload Text
            if folder_id_input:
                st.write("☁️ Uploading Text to Drive...")
                text_content = f"HEADLINE: {headline}\n\nBODY: {body}\n\nPROMPT: {img_prompt}\n\nSOURCE: {url_input}"
                with open("temp_text.txt", "w") as f: f.write(text_content)
                doc_link = upload_to_drive(creds, folder_id_input, f"{base_name}.txt", "temp_text.txt", "text/plain")
            
            status.update(label="Complete!", state="complete", expanded=False)

            # --- RESULT DISPLAY ---
            with col2:
                st.subheader("3. Final Result")
                
                # Show Image
                if generated_image: 
                    st.image(local_img_name, caption="Generated by Imagen")
                else:
                    st.warning("Image Blocked (Safety Filter)")

                # Show Links
                if folder_id_input:
                    if img_link or doc_link:
                        st.success(f"✅ Saved to Drive Folder: {folder_id_input}")
                        if img_link: st.markdown(f"📂 [View Image in Drive]({img_link})")
                        if doc_link: st.markdown(f"📄 [View Text in Drive]({doc_link})")
                    else:
                        st.error("❌ Save Failed. Did you share the folder with the Robot Email? (Check Sidebar)")
                
                st.divider()
                st.text_input("Headline", value=headline)
                st.text_area("Body", value=body, height=150)
