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
st.set_page_config(page_title="Agency SEO Writer", page_icon="🏥", layout="wide")

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
        selected_model = st.selectbox("Text Model", ["gemini-2.5-pro", "gemini-2.5-flash"])
        temp = st.slider("Creativity", 0.0, 1.0, 0.2)
        
        st.divider()
        st.info("""
        **✅ Quality Checklist:**
        
        1. **Visuals:**
           - *Lifestyle:* High-end, happy, healed.
           - *UGC:* Authentic, selfie-style, imperfect.
           
        2. **Logic (New):**
           - Detects "Care" contexts (e.g., Plan of Care = People, not Paperwork).
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

    # --- 1. INTELLIGENT CONTEXT DETECTION (The "Care" Logic) ---
    context_logic = """
    **VISUAL CONTEXT RULES:**
    1. **Analyze the Topic:** Does this involve caregiving, family, or sensitive health topics?
    2. **Avoid Literalism:** If the topic is "Plan of Care" or "Consultation", DO NOT describe documents, pens, or empty chairs.
    3. **Focus on People:** Always depict the *human outcome* or *connection*.
       - If Senior Care: Show a warm interaction between a Senior and a Family Member.
    """

    # --- 2. STYLE SELECTION (Updated with Hand Safety) ---
    if visual_style == "UGC / Selfie Style":
        visual_instruction = """
        Describe a **'UGC / Selfie-Style'** photo.
        - **Vibe:** Authentic, candid, slightly imperfect (iPhone aesthetic).
        - **Subject:** A real person (or family) looking happy and relieved. 
        - **Pose:** Heads leaning together affectionately (cheek to cheek). 
        - **CRITICAL SAFETY:** HANDS MUST BE HIDDEN or resting naturally on laps. NO disembodied hands on shoulders. NO complex hugging poses that risk extra limbs.
        - **Constraint:** NO professional studio lighting. Make it look like social media content.
        """
    elif visual_style == "Lifestyle / Commercial":
        visual_instruction = """
        Describe a **'High-End Commercial Portrait'**.
        - **Vibe:** Magazine quality, aspirational, successful outcome.
        - **Subject:** Attractive, vibrant adult (30s-50s) at their absolute best.
        - **Technique:** 85mm lens, shallow depth of field (bokeh), soft lighting.
        - **Constraint:** NO hands touching face in pain. NO complex hand gestures near the face to avoid anatomy errors.
        """
    else: # Office / Atmosphere
        visual_instruction = """
        Describe a **'Modern Medical/Office Interior'**.
        - **Vibe:** Clean, sunlit, welcoming, expensive.
        - **Details:** Fresh flowers, modern furniture, soft focus background.
        - **Constraint:** NO PEOPLE. NO Dental chairs unless specified.
        """

    prompt = f"""
    Role: SEO Copywriter.
    Context: {text} | Focus: {focus} | Keyword: {keyword}
    Task: {task}
    
    Guidelines: 
    1. Start Immediately. Tone: {tone}. No fluff.
    2. Mandatory Keyword: {keyword if keyword else "N/A"}.
    
    *** IMAGE PROMPT LOGIC ({visual_style}) ***:
    {context_logic}
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
        # Base modifiers to ensure quality across all styles
        modifiers = "4k, high quality, anatomically correct hands"
        if "UGC" in prompt or "Selfie" in prompt:
            modifiers += ", shot on iPhone, social media style, authentic"
        else:
            modifiers += ", photorealistic, professional photography"
            
        images = model.generate_images(prompt=prompt + ", " + modifiers, number_of_images=1, aspect_ratio="4:3", person_generation="allow_adult")
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
    
    # Updated Visual Styles to include UGC
    visual_style = st.radio("Image Style", ["Lifestyle / Commercial", "UGC / Selfie Style", "Office / Atmosphere"], horizontal=True)

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
            
            # --- ROBUST ERROR HANDLING & DEBUGGING ---
            try:
                raw = generate_copy(site_text, focus_input, keyword_input, selected_model, temp, post_type, vibe, visual_style)
                
                # 1. Parsing Headline
                headline_match = re.search(r'\*?HEADLINE:\*?\s*(.*)', raw, re.IGNORECASE)
                headline = headline_match.group(1).strip() if headline_match else "Header Not Found"

                # 2. Parsing Body
                body_match = re.search(r'\*?BODY:\*?\s*(.*?)\s*\*?IMAGE_PROMPT:', raw, re.DOTALL | re.IGNORECASE)
                body = body_match.group(1).strip() if body_match else "Body Not Found"

                # 3. Parsing Image Prompt
                img_prompt_match = re.search(r'\*?IMAGE_PROMPT:\*?\s*(.*)', raw, re.IGNORECASE)
                img_prompt = img_prompt_match.group(1).strip() if img_prompt_match else "SKIP"

            except Exception as e:
                headline = "Error Parsing Output"
                body = f"The AI generated the text, but the code couldn't read it.\n\nRaw Error: {str(e)}\n\nAI Output:\n{raw}"
                img_prompt = "SKIP"

            generated_image = None
            if post_type == "Service Highlight" and img_prompt != "SKIP":
                st.write("📸 Generating AI Photo...")
                generated_image = generate_ai_image(img_prompt)
            else:
                st.write("⏩ Skipping Image Gen (Use Template)")
            
            status.update(label="Done!", state="complete", expanded=False)

            # --- RESULT ---
            with col2:
                st.subheader("3. Copy & Assets")
                
                if generated_image:
                    generated_image.save("temp.jpg")
                    st.image("temp.jpg", caption=f"AI Generated ({visual_style})")
                    with open("temp.jpg", "rb") as f:
                        st.download_button("⬇️ Download AI Photo", f, "ai_photo.jpg", "image/jpeg")
                
                st.text_input("Headline", headline)
                st.text_area("Caption", body, height=200)
                st.caption(f"Prompt: {img_prompt}")
