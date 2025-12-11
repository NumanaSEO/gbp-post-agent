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
    st.title("⚙️ Config")
    
    # AUTH CHECK
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
        selected_model = st.selectbox("Text Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-001"])
        temp = st.slider("Creativity", 0.0, 1.0, 0.2)
        
        st.divider()
        st.info("""
        **✅ Quality Checklist:**
        
        1. **Visuals:**
           - *Lifestyle:* Is the person fully healed & happy? (No bandages).
           - *Office:* Is it clean/empty?
           
        2. **Accuracy:**
           - Did it create a Dental Chair for a Medical Doctor? (Bad).
           
        3. **Tone:**
           - Did it say "Unleash"? (Re-run it).
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

def generate_copy(text, focus, keyword, model_name, temp, post_type, vibe, visual_style):
    model = GenerativeModel(model_name)
    
    tone = "Warm, friendly"
    if vibe == "Luxury": tone = "Sophisticated, polished"
    elif vibe == "Urgent": tone = "Direct, concise"

    task = f"Highlight service benefits. Focus: {focus}."
    if post_type == "Review Spotlight":
        task = "Write a short 'Thank You' caption for a patient review."
    elif post_type == "FAQ":
        task = f"Answer a common patient question about: {focus}."

    # --- STRICT VISUAL LOGIC (UPDATED WITH POSITIVE CONSTRAINTS) ---
    if visual_style == "Lifestyle / People (Headshots)":
        visual_instruction = """
        Describe a 'High-End Commercial Beauty/Lifestyle Portrait'.
        - **CONCEPT:** The image must represent the *aspirational outcome* of successful treatment: vitality, confidence, and happiness.
        - **SUBJECT:** An attractive, vibrant adult (30s-50s) at their absolute best. Look energized and healthy.
        - **EXPRESSION:** A genuine, warm, confident smile. Eyes are bright and engaged with the camera.
        
        - **POSE (CRITICAL SAFETY):** - To prevent accidental 'headache' gestures, use specific positive pose instructions:
          - **PRIMARY OPTION:** "Arms crossed confidently over the chest, shoulders back."
          - **SECONDARY OPTION:** "Hands resting casually in pockets."
          - **CONSTRAINT:** Hands must be clearly visible and kept AWAY from the face, neck, and head.
        
        - **BACKGROUND:** Neutral Studio Grey, Bright Living Room, or Soft Outdoor Blur. (Keep it simple, high-end).
        - **STYLE:** Magazine photography, soft flattering lighting, 85mm lens, shallow depth of field.

        - **SAFETY OVERRIDE:**
          - The person must look 100% VIBRANT and HEALTHY.
          - DO NOT show bandages, doctors, hospitals, pill bottles, or medical tools.
          - **NEGATIVE CONSTRAINT:** NO THUMBS UP. NO hands touching face.
        """
    else:
        visual_instruction = """
        Describe a 'Modern Medical Interior'.
        - If Plastic Surgery: "A high-end, marble consultation desk with a modern computer and a white orchid. Soft depth of field."
        - If OB/GYN: "Clean, comfortable medical room, soft lighting." (NO DENTAL CHAIRS).
        - General: "Sunlit reception area with plants."
        - **NEGATIVE CONSTRAINT:** NO PEOPLE.
        """

    prompt = f"""
    Role: SEO Copywriter.
    Context: {text} | Focus: {focus} | Keyword: {keyword}
    Task: {task}
    
    Guidelines: 
    1. Start Immediately. Tone: {tone}. No fluff.
    2. Mandatory Keyword: {keyword if keyword else "N/A"}.
    
    *** IMAGE RULE ({visual_style}) ***:
    {visual_instruction}
    - If Review/FAQ: Return "SKIP".

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
        # Ensure we allow adults for lifestyle shots
        images = model.generate_images(prompt=prompt+", photorealistic, 4k, no text", number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
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
    
    visual_style = st.radio("Image Style", ["Office / Atmosphere (Safe)", "Lifestyle / People (Headshots)"], horizontal=True)

    st.subheader("2. Inputs")
    url_input = st.text_input("URL", placeholder="client.com/service")
    keyword_input = st.text_input("Keyword", placeholder="Dentist 78704")
    
    focus_label = "Focus / Offer"
    if post_type == "Review Spotlight": focus_label = "Paste Review Text"
    elif post_type == "FAQ": focus_label = "Question to Answer"
    focus_input = st.text_input(focus_label)
    
    st.write("") 
    run_btn = st.button("✨ Generate Copy", type="primary")

    if run_btn and auth_ready and url_input:
        with st.status("Agent working...", expanded=True) as status:
            st.write("🕷️ Reading site...")
            site_text = get_website_text(url_input)
            
            st.write("🧠 Writing SEO Copy...")
            try:
                raw = generate_copy(site_text, focus_input, keyword_input, selected_model, temp, post_type, vibe, visual_style)
                headline = raw.split("HEADLINE:")[1].split("BODY:")[0].strip()
                body = raw.split("BODY:")[1].split("IMAGE_PROMPT:")[0].strip()
                img_prompt = raw.split("IMAGE_PROMPT:")[1].strip()
            except: headline="Error"; body="Error"; img_prompt="SKIP"

            generated_image = None
            if post_type == "Service Highlight":
                st.write("📸 Generating AI Photo...")
                generated_image = generate_ai_image(img_prompt)
            else:
                st.write("⏩ Skipping Image Gen (Use Template)")
            
            status.update(label="Done!", state="complete", expanded=False)

            # --- RESULT ---
            with col2:
                st.subheader("3. Copy & Assets")
                
                if post_type != "Service Highlight":
                    st.info("ℹ️ **Instruction:** Use a Template from Drive for this post type.")
                elif generated_image:
                    generated_image.save("temp.jpg")
                    st.image("temp.jpg", caption=f"AI Generated ({visual_style})")
                    with open("temp.jpg", "rb") as f:
                        st.download_button("⬇️ Download AI Photo", f, "ai_photo.jpg", "image/jpeg")
                
                st.text_input("Headline", headline)
                st.text_area("Caption", body, height=200)
                st.caption(f"Prompt: {img_prompt}")
