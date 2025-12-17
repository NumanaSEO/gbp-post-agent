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
st.set_page_config(page_title="Agency SEO Writer", page_icon="🧸", layout="wide")

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
            vertexai.init(project=st.secrets["gcp_service_account"]["project_id"], location="us-central1", credentials=creds)
            auth_ready = True
            st.success("✅ Connected")
        except: st.error("Auth Failed")
    
    if auth_ready:
        st.divider()
        st.subheader("🧠 Model")
        selected_model = st.selectbox("Text Model", ["gemini-2.5-pro", "gemini-2.5-flash"])
        temp = st.slider("Creativity", 0.0, 1.0, 0.4)
        bulk_count = st.slider("Number of Posts to Generate", 1, 12, 1)
        
        visual_style = st.radio("Image Style", ["Lifestyle / Commercial", "UGC / Selfie Style", "Office / Atmosphere"], horizontal=True)

# --- FUNCTIONS ---
def generate_copy(text, focus, keyword, model_name, temp, post_type, vibe, visual_style, iteration):
    model = GenerativeModel(model_name)
    prompt = f"""
    Role: SEO Copywriter. Variation #{iteration} of {bulk_count}.
    Context: {text} | Focus: {focus} | Keyword: {keyword}
    Task: Write a unique {post_type} with a {vibe} vibe. 
    Style: {visual_style}
    
    Output Format:
    HEADLINE: [Header]
    BODY: [Body]
    IMAGE_PROMPT: [Prompt or SKIP]
    """
    response = model.generate_content(prompt, generation_config={"temperature": temp})
    return response.text

def generate_ai_image(prompt):
    if not prompt or "SKIP" in prompt: return None
    try:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        images = model.generate_images(prompt=prompt, number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
        return images[0]
    except: return None

# --- MAIN UI ---
st.title("✍️ Agency SEO Writer")
url_input = st.text_input("URL")
keyword_input = st.text_input("Keyword")
focus_input = st.text_input("Focus / Offer")
run_btn = st.button(f"✨ Generate {bulk_count} Posts")

if run_btn and auth_ready:
    # Use a list to store results for this session
    all_posts = []
    
    # 1. Scrape Site Once
    headers = {'User-Agent': 'Mozilla/5.0'}
    site_text = requests.get(url_input, headers=headers).text[:5000]

    # 2. Loop for Bulk Generation
    for i in range(1, bulk_count + 1):
        with st.status(f"Creating Post {i}...") as status:
            # Generate Text
            raw = generate_copy(site_text, focus_input, keyword_input, selected_model, temp, "Service", "Friendly", visual_style, i)
            
            # Parse Text
            h = re.search(r'HEADLINE:\s*(.*)', raw, re.IGNORECASE)
            b = re.search(r'BODY:\s*(.*?)\s*IMAGE_PROMPT:', raw, re.DOTALL | re.IGNORECASE)
            p = re.search(r'IMAGE_PROMPT:\s*(.*)', raw, re.IGNORECASE)
            
            headline = h.group(1) if h else f"Post {i}"
            body = b.group(1) if b else "Content generation failed."
            img_p = p.group(1) if p else "SKIP"

            # Generate Unique Image
            img_obj = None
            if img_p != "SKIP":
                img_obj = generate_ai_image(img_p)
            
            # Store result in our temporary "database" list
            all_posts.append({
                "headline": headline,
                "body": body,
                "image": img_obj,
                "prompt": img_p
            })
            status.update(label=f"✅ Post {i} Ready", state="complete")

    # 3. Display All Results
    st.divider()
    for idx, post in enumerate(all_posts):
        with st.container(border=True):
            col_img, col_txt = st.columns([1, 2])
            with col_img:
                # SAFETY CHECK: Only try to save/show if image is NOT None
                if post["image"] is not None:
                    buf = io.BytesIO()
                    post["image"].save(buf, format="JPEG")
                    st.image(buf)
                    st.download_button(f"Download Image {idx+1}", buf.getvalue(), f"img_{idx+1}.jpg")
                else:
                    st.warning("No image generated for this post.")
            
            with col_txt:
                st.subheader(post["headline"])
                st.write(post["body"])
