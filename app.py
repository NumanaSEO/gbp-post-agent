import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account
import requests
from bs4 import BeautifulSoup
import io
import re

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
        # Using gemini-2.5-pro as it has been working best for you
        selected_model = st.selectbox("Text Model", ["gemini-2.5-pro", "gemini-2.5-flash"])
        temp = st.slider("Creativity", 0.0, 1.0, 0.4)
        
        st.divider()
        st.info("**Strategy:** One-at-a-time generation for maximum quality and stability.")

# --- FUNCTIONS ---
def get_website_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        return " ".join([p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])])[:5000].strip()
    except: return None

def generate_copy(text, focus, keyword, model_name, temp, post_type, vibe, visual_style):
    model = GenerativeModel(model_name)
    
    # Custom Tone & Context Logic
    context_logic = """
    **VISUAL CONTEXT RULES:**
    - ABA/Kids: NO children. Use colorful therapy rooms, toys, or Therapist POV.
    - Senior Care: Warm interaction between Senior and Caregiver.
    - General: Focus on the human outcome/benefit.
    """

    if visual_style == "UGC / Selfie Style":
        visual_instruction = "Describe a 'UGC / Selfie-Style' photo. Authentic, candid, iPhone aesthetic."
    elif visual_style == "Lifestyle / Commercial":
        visual_instruction = "Describe a 'High-End Commercial Portrait'. 85mm lens, bokeh."
    else:
        visual_instruction = "Describe a 'Modern Interior'. Clean, sunlit, welcoming."

    prompt = f"""
    Role: SEO Copywriter.
    Context: {text} | Focus: {focus} | Keyword: {keyword}
    Task: Write a {vibe} {post_type}.
    
    *** IMAGE PROMPT LOGIC ({visual_style}) ***:
    {context_logic}
    {visual_instruction}

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
        # Ensure we always add photorealistic modifiers
        full_prompt = f"{prompt}, 4k, high quality, photorealistic"
        images = model.generate_images(prompt=full_prompt, number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
        return images[0]
    except: return None

# --- MAIN UI ---
st.title("✍️ Agency SEO Writer")
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Strategy")
    c1, c2 = st.columns(2)
    with c1: post_type = st.selectbox("Post Type", ["Service Highlight", "Review Spotlight", "FAQ"])
    with c2: vibe = st.selectbox("Brand Vibe", ["Friendly", "Luxury", "Urgent"])
    
    visual_style = st.radio("Image Style", ["Lifestyle / Commercial", "UGC / Selfie Style", "Office / Atmosphere"], horizontal=True)

    st.subheader("2. Inputs")
    url_input = st.text_input("URL", placeholder="client.com/service")
    keyword_input = st.text_input("Keyword", placeholder="e.g. medical weight loss")
    focus_input = st.text_input("Focus / Offer")
    
    run_btn = st.button("✨ Generate Post", type="primary")

# --- GENERATION LOGIC ---
if run_btn and auth_ready and url_input:
    with st.status("Creating your post...", expanded=True) as status:
        st.write("🕷️ Reading site...")
        site_text = get_website_text(url_input)
        
        st.write("🧠 Writing SEO Copy...")
        raw_output = generate_copy(site_text, focus_input, keyword_input, selected_model, temp, post_type, vibe, visual_style)
        
        # Regex Parsing
        h_match = re.search(r'HEADLINE:\s*(.*)', raw_output, re.IGNORECASE)
        b_match = re.search(r'BODY:\s*(.*?)\s*IMAGE_PROMPT:', raw_output, re.DOTALL | re.IGNORECASE)
        p_match = re.search(r'IMAGE_PROMPT:\s*(.*)', raw_output, re.IGNORECASE)
        
        headline = h_match.group(1).strip() if h_match else "Headline Not Found"
        body = b_match.group(1).strip() if b_match else "Body Not Found"
        img_p = p_match.group(1).strip() if p_match else "SKIP"

        # Image Gen with safety check
        generated_image = None
        if img_p != "SKIP":
            st.write("📸 Generating AI Photo...")
            generated_image = generate_ai_image(img_p)
        
        status.update(label="✅ Done!", state="complete", expanded=False)

    # --- RESULT DISPLAY ---
    with col2:
        st.subheader("3. Copy & Assets")
        if generated_image:
            buf = io.BytesIO()
            generated_image.save(buf, format="JPEG")
            st.image(buf, caption=f"AI Generated ({visual_style})")
            st.download_button("⬇️ Download Photo", buf.getvalue(), "photo.jpg", "image/jpeg")
        elif img_p != "SKIP":
            st.warning("Image generation was skipped or filtered. Try a different focus.")

        st.text_input("Headline", headline)
        st.text_area("Caption", body, height=250)
        st.caption(f"Used Prompt: {img_p}")
