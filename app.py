import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account
import requests
from bs4 import BeautifulSoup
import io
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Agency Post Factory", page_icon="🏥", layout="wide")

# --- CSS ---
st.markdown("""
    <style>
    .stButton>button {width: 100%; border-radius: 5px; height: 3em; font-weight: bold;} 
    div[data-testid="stStatusWidget"] {border: 1px solid #ddd; border-radius: 10px; padding: 10px;}
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR: CONFIG ---
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # 1. AUTHENTICATION
    st.subheader("1. System Status")
    auth_ready = False
    
    if "gcp_service_account" in st.secrets:
        try:
            # Load Creds (Only Cloud Platform scope needed now)
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            project_id = st.secrets["gcp_service_account"]["project_id"]
            
            # Initialize Vertex
            vertexai.init(project=project_id, location="us-central1", credentials=creds)
            auth_ready = True
            st.success(f"✅ AI System Online")
        except Exception as e:
            st.error(f"Secrets Error: {e}")
    else:
        st.warning("⚠️ No Secrets found.")

    # 2. AI SETTINGS
    if auth_ready:
        st.divider()
        st.subheader("🧠 Model Settings")
        # Updated Model List (Exact IDs)
        selected_model_name = st.selectbox(
            "Text Model", 
            ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-001"], 
            index=0
        )
        temperature = st.slider("Creativity", 0.0, 1.0, 0.2)
        
        st.divider()
        st.info("""
        **GBP Checklist:**
        1. **Safe Image?** (No people/kids)
        2. **No Fluff?** (No "Unleash/Elevate")
        3. **SEO?** (Keyword included)
        """)

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
    You are a Front Desk Receptionist for a medical practice. Write a Google Business Profile update.
    
    CONTEXT: {text} 
    FOCUS: {focus_topic} 
    KEYWORD: {keyword}
    
    STRICT GUIDELINES:
    1. **No Fluff:** Ban words like "Unleash", "Elevate", "Transform", "Magic".
    2. **Start Immediately:** Do NOT say "Hello from [Name]" or "We want to share." Start directly with the problem or the keyword.
    3. **Tone:** Warm, professional, Grade 8 English.
    4. {keyword_instruction}
    
    IMAGE SAFETY: If topic involves CHILDREN/PATIENTS, prompt for a ROOM/OBJECT photo. NO PEOPLE.

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
        # Fallback to Imagen 2
        try:
            model = ImageGenerationModel.from_pretrained("imagegeneration@006")
            images = model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
            return images[0]
        except: return None

# --- MAIN UI ---

st.title("🏥 GBP Post Factory")
st.markdown("Generate **Entity-Optimized Content**.")
st.divider()

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Input Details")
    url_input = st.text_input("Service Page URL", placeholder="https://client.com/service")
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1: keyword_input = st.text_input("Target Keyword", placeholder="e.g. Dentist 78704")
    with sub_col2: focus_input = st.text_input("Focus/Offer", placeholder="e.g. Summer Special")
    
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
            
            # 4. Process Image for Display
            local_img_name = "temp_image.jpg"
            if generated_image:
                # We still save to a local temp file because Vertex SDK requires it
                generated_image.save(local_img_name, include_generation_parameters=False)
            
            status.update(label="Complete!", state="complete", expanded=False)

            # --- RESULT DISPLAY ---
            with col2:
                st.subheader("2. Final Result")
                
                # Show Image
                if generated_image: 
                    st.image(local_img_name, caption="Generated by Imagen")
                    
                    # Create Download Button
                    with open(local_img_name, "rb") as f:
                        btn = st.download_button(
                            label="⬇️ Download Image",
                            data=f,
                            file_name="post_image.jpg",
                            mime="image/jpeg"
                        )
                else:
                    st.warning("Image Blocked (Safety Filter)")

                st.divider()
                st.text_input("Headline", value=headline)
                st.text_area("Body", value=body, height=150)
                st.caption(f"Prompt Used: {img_prompt}")
