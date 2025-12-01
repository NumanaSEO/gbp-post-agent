import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account
import requests
from bs4 import BeautifulSoup
import io

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
    
    # AUTH CHECK
    auth_ready = False
    if "gcp_service_account" in st.secrets:
        try:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            # Initialize Vertex (Defaulting to us-central1)
            vertexai.init(project=st.secrets["gcp_service_account"]["project_id"], location="us-central1", credentials=creds)
            auth_ready = True
            st.success("✅ AI System Online")
        except:
            st.error("Authentication Failed")
    else:
        st.warning("⚠️ No Secrets Found")

    if auth_ready:
        st.divider()
        st.subheader("🧠 Model Settings")
        selected_model = st.selectbox("Text Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-001"])
        temp = st.slider("Creativity", 0.0, 1.0, 0.2)
        
        st.divider()
        st.info("""
        **GBP Post Quality Checklist:**
        
        1. **Tone Check:**
           - No "Unleash", "Elevate", or "Unlock".
           - Does it sound like a helpful human?
           
        2. **SEO Check:**
           - Is the Target Keyword included naturally?
           
        3. **Visual Check:**
           - **Service:** AI Photo (Must be empty room/object).
           - **Review:** Use the **5-Star Template** from Drive.
           - **FAQ:** Use the **Q&A Template** from Drive.
        """)

# --- FUNCTIONS ---

def get_website_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        text = " ".join([p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])])
        return text[:5000].strip()
    except: return None

def generate_copy(text, focus, keyword, model_name, temp, post_type, vibe):
    model = GenerativeModel(model_name)
    
    tone = "Warm, friendly, helpful. Grade 8 English."
    if vibe == "High-End / Luxury": tone = "Sophisticated, polished, professional."
    elif vibe == "Urgent / Direct": tone = "Direct, concise, action-oriented."

    # Task Definition
    task = f"Highlight service benefits found in text. Focus on: {focus}."
    if post_type == "Review Spotlight":
        task = "The Focus Input is a review. Write a short 'Thank You' caption. Summarize the sentiment."
    elif post_type == "FAQ / Education":
        task = f"Write a 'Did You Know?' or 'FAQ' post based on context. Answer a common question about: {focus}."

    prompt = f"""
    Role: SEO Copywriter for Local Business.
    Context: {text} | Focus: {focus} | Keyword: {keyword}
    Task: {task}
    
    Guidelines: 
    1. Start Immediately (No "Hello/We want to share").
    2. Tone: {tone}. No fluff words ("Unleash", "Elevate").
    3. Mandatory Keyword: {keyword if keyword else "N/A"}.
    
    Image Prompt Rule:
    - If Service Highlight: Describe a specific room/object (NO PEOPLE).
    - If Review or FAQ: Return "SKIP".

    Output Format:
    HEADLINE: [Header]
    BODY: [Body]
    IMAGE_PROMPT: [Prompt or SKIP]
    """
    response = model.generate_content(prompt, generation_config={"temperature": temp})
    return response.text

def generate_ai_image(prompt):
    if not prompt or "SKIP" in prompt or "Error" in prompt: return None
    try:
        model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
        images = model.generate_images(prompt=prompt+", photorealistic, 4k, no text", number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
        return images[0]
    except: return None

# --- MAIN UI ---

st.title("✍️ GBP Post Generator")
st.markdown("Generate optimized captions. **Images generated only for Service Highlights.**")
st.divider()

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Strategy")
    c1, c2 = st.columns(2)
    with c1: post_type = st.selectbox("Post Type", ["Service Highlight", "Review Spotlight", "FAQ / Education"])
    with c2: vibe = st.selectbox("Brand Vibe", ["Friendly / Warm", "High-End / Luxury", "Urgent / Direct"])

    st.subheader("2. Inputs")
    url_input = st.text_input("Service Page URL", placeholder="https://client.com/service")
    
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1: 
        keyword_input = st.text_input("Target Keyword", placeholder="e.g. Dentist 78704")
    with sub_col2: 
        focus_label = "Focus / Offer"
        if post_type == "Review Spotlight": focus_label = "Paste Review Text"
        elif post_type == "FAQ / Education": focus_label = "Question to Answer"
        focus_input = st.text_input(focus_label)
    
    st.write("") 
    run_btn = st.button("✨ Generate Copy", type="primary")

    if run_btn:
        if not auth_ready: st.error("Check Sidebar Auth"); st.stop()
        if not url_input: st.warning("Enter URL"); st.stop()

        with st.status("Agent working...", expanded=True) as status:
            st.write("🕷️ Reading site...")
            site_text = get_website_text(url_input)
            
            st.write("🧠 Writing SEO Copy...")
            try:
                raw = generate_copy(site_text, focus_input, keyword_input, selected_model, temp, post_type, vibe)
                headline = raw.split("HEADLINE:")[1].split("BODY:")[0].strip()
                body = raw.split("BODY:")[1].split("IMAGE_PROMPT:")[0].strip()
                img_prompt = raw.split("IMAGE_PROMPT:")[1].strip()
            except: 
                headline="Error"; body="Error"; img_prompt="SKIP"

            # LOGIC: Only generate image for Service Highlights
            generated_image = None
            if post_type == "Service Highlight":
                st.write("📸 Generating AI Room Photo...")
                generated_image = generate_ai_image(img_prompt)
            else:
                st.write("⏩ Skipping Image Gen (Template Required)")
            
            status.update(label="Done!", state="complete", expanded=False)

            # --- RESULT ---
            with col2:
                st.subheader("3. Copy & Assets")
                
                # VISUAL INSTRUCTIONS (The "Traffic Cop")
                if post_type == "Review Spotlight":
                    st.warning("🖼️ **ACTION REQUIRED:** Attach '5-Star Template' from Drive.")
                elif post_type == "FAQ / Education":
                    st.info("🖼️ **ACTION REQUIRED:** Attach 'Q&A Template' or Real Photo.")
                elif generated_image:
                    generated_image.save("temp.jpg")
                    st.image("temp.jpg", caption="AI Generated Room")
                    with open("temp.jpg", "rb") as f:
                        st.download_button("⬇️ Download AI Photo", f, "ai_photo.jpg", "image/jpeg")
                elif not generated_image and post_type == "Service Highlight":
                    st.error("Image Generation Failed (Safety Filter). Use Real Photo.")
                
                st.text_input("Headline", headline)
                st.text_area("Caption", body, height=250)
