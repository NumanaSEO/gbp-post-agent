import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account
import requests
from bs4 import BeautifulSoup
import io
import re
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Bulk SEO Agent", page_icon="🧸", layout="wide")

# --- SIDEBAR: CONFIG ---
with st.sidebar:
    st.title("⚙️ Config")
    
    auth_ready = False
    if "gcp_service_account" in st.secrets:
        try:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            # Use "global" or "us-central1" based on your project's availability
            vertexai.init(project=st.secrets["gcp_service_account"]["project_id"], location="us-central1", credentials=creds)
            auth_ready = True
            st.success("✅ Connected")
        except Exception as e: st.error(f"Auth Failed: {e}")
    
    if auth_ready:
        st.divider()
        st.subheader("🧠 Model Settings")
        # Defaulting to 2.5 series as per your successful tests
        selected_model = st.selectbox("Text Model", ["gemini-2.5-pro", "gemini-2.5-flash"])
        temp = st.slider("Creativity", 0.0, 1.0, 0.7)
        bulk_count = st.slider("Number of Posts to Generate", 1, 12, 1) # BULK CONTROL

# --- FUNCTIONS ---
def get_website_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        return " ".join([p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])])[:5000].strip()
    except: return ""

def generate_single_post(text, focus, keyword, model_name, temp, post_type, vibe, visual_style, iteration):
    model = GenerativeModel(model_name)
    
    # Adding 'iteration' to the prompt ensures the AI creates variety in bulk runs
    prompt = f"""
    Role: SEO Copywriter. Post #{iteration} of {bulk_count}.
    Context: {text} | Focus: {focus} | Keyword: {keyword}
    Task: Write a unique {post_type} with a {vibe} vibe. 
    
    Output Format:
    HEADLINE: [Header]
    BODY: [Body]
    IMAGE_PROMPT: [Detailed prompt for Imagen 3]
    """
    response = model.generate_content(prompt, generation_config={"temperature": temp})
    return response.text

def generate_ai_image(prompt):
    try:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        images = model.generate_images(prompt=prompt, number_of_images=1, person_generation="allow_adult")
        return images[0]
    except: return None

# --- MAIN UI ---
st.title("✍️ Bulk SEO Agent")
url_input = st.text_input("Website URL")
keyword_input = st.text_input("Main Keyword")
focus_input = st.text_area("Specific Focus/Offer (comma-separated for variety)")

if st.button("🚀 Start Bulk Generation") and auth_ready:
    site_content = get_website_text(url_input)
    
    # Main loop for bulk creation
    for i in range(1, bulk_count + 1):
        with st.container(border=True):
            st.subheader(f"Post {i} of {bulk_count}")
            
            with st.spinner(f"Generating content for post {i}..."):
                raw_output = generate_single_post(site_content, focus_input, keyword_input, selected_model, temp, "Service Highlight", "Friendly", "Lifestyle", i)
                
                # Parsing
                h_match = re.search(r'HEADLINE:\s*(.*)', raw_output, re.IGNORECASE)
                b_match = re.search(r'BODY:\s*(.*?)\s*IMAGE_PROMPT:', raw_output, re.DOTALL | re.IGNORECASE)
                p_match = re.search(r'IMAGE_PROMPT:\s*(.*)', raw_output, re.IGNORECASE)
                
                headline = h_match.group(1) if h_match else "Header"
                body = b_match.group(1) if b_match else "Body"
                img_p = p_match.group(1) if p_match else ""

            colA, colB = st.columns([1, 2])
            with colA:
                if img_p:
                    img = generate_ai_image(img_p)
                    if img:
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        st.image(buf)
                        st.download_button(f"Download Image {i}", buf.getvalue(), f"post_{i}.jpg")
            
            with colB:
                st.write(f"**{headline}**")
                st.write(body)
                st.caption(f"Prompt: {img_p}")
        
        # Small sleep to prevent rate limiting in fast bulk runs
        time.sleep(1)
