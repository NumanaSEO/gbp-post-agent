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
    
    # 1. AUTHENTICATION
    st.subheader("1. System Status")
    auth_ready = False
    
    if "gcp_service_account" in st.secrets:
        try:
            # Load Creds (Only Cloud Platform scope needed)
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
        selected_model_name = st.selectbox(
            "Text Model", 
            ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-001"], 
            index=0
        )
        temperature = st.slider("Creativity", 0.0, 1.0, 0.2)
        
        st.divider()
        st.subheader("📸 Real Photo Override")
        uploaded_file = st.file_uploader("Upload Client Photo", type=['jpg', 'png', 'jpeg'], help="If you upload a photo here, the AI Image Generator will be skipped.")

        # 3. GBP Post CHECKLIST (RESTORED)
        st.divider()
        st.info("""
        **VA Quality Checklist:**
        1. **Safe Image?** (No people/kids if AI generated).
        2. **Accurate?** (Is it an Exam Table or a Dental Chair?).
        3. **No Fluff?** (Did it say "Unleash"? Re-run it).
        4. **SEO?** (Target Keyword included naturally?).
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

def generate_post_content(text, focus_input, keyword, model_name, temp, post_type, vibe):
    model = GenerativeModel(model_name)
    
    # 1. TONE LOGIC
    tone_instruction = "Tone: Warm, friendly, helpful. Grade 8 English."
    if vibe == "High-End / Luxury":
        tone_instruction = "Tone: Sophisticated, polished, exclusive, professional. Grade 10 English."
    elif vibe == "Urgent / Direct":
        tone_instruction = "Tone: Direct, concise, action-oriented. Short sentences."

    # 2. POST TYPE LOGIC
    task_instruction = f"Write a post highlighting the benefits of the service found in CONTEXT. Focus on: {focus_input}."
    if post_type == "Review Spotlight":
        task_instruction = f"The 'FOCUS INPUT' provided is a patient review (or topic). Write a 'Thank You' post appreciating the feedback."
    elif post_type == "FAQ / Education":
        task_instruction = f"Write a 'Did You Know?' or 'FAQ' post based on the CONTEXT. Answer a common patient question related to: {focus_input}."

    keyword_instruction = f"MANDATORY: Include '{keyword}'." if keyword else ""
    
    prompt = f"""
    You are a Social Media Manager for a medical practice. Write a Google Business Profile update.
    
    CONTEXT SOURCE: {text}
    FOCUS INPUT: {focus_input}
    KEYWORD: {keyword}
    
    TASK: {task_instruction}
    
    STRICT GUIDELINES:
    1. **Start Immediately:** No "Hello from..." or "We want to share." Start with the problem/solution.
    2. **No Fluff:** Ban "Unleash", "Elevate", "Magic", "Realm".
    3. {tone_instruction}
    4. {keyword_instruction}
    
    *** IMAGE VISUAL RULES (CRITICAL) ***: 
    1. **Safety:** If topic involves CHILDREN/PATIENTS, prompt for a ROOM/OBJECT photo (No People).
    2. **Accuracy:** Look at the medical specialty in the CONTEXT. 
       - If OB/GYN or General Doctor: Specify "FLAT Medical Examination Table with paper roll". **DO NOT GENERATE A CHAIR.**
       - If Dentist: Specify "Dental chair".
       - If Therapy: Specify "Comfortable couch, soft lighting, rug".
       - If in doubt: Specify "A modern, tidy medical consultation desk with computer".

    OUTPUT FORMAT:
    HEADLINE: [Header]
    BODY: [Body]
    IMAGE_PROMPT: [Prompt based on Visual Rules]
    """
    
    response = model.generate_content(prompt, generation_config={"temperature": temp})
    return response.text

def generate_image(prompt):
    # Skip if prompt is empty/error
    if not prompt or prompt == "Error": return None

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
    st.subheader("1. Strategy")
    c1, c2 = st.columns(2)
    with c1:
        post_type = st.selectbox("Post Type", ["Service Highlight", "Review Spotlight", "FAQ / Education"])
    with c2:
        vibe = st.selectbox("Brand Vibe", ["Friendly / Warm", "High-End / Luxury", "Urgent / Direct"])

    st.subheader("2. Inputs")
    url_input = st.text_input("Service Page URL", placeholder="https://client.com/service")
    
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1: 
        keyword_input = st.text_input("Target Keyword", placeholder="e.g. Dentist 78704")
    with sub_col2: 
        focus_label = "Focus / Offer"
        if post_type == "Review Spotlight": focus_label = "Paste Review Text Here"
        elif post_type == "FAQ / Education": focus_label = "Question to Answer"
        focus_input = st.text_input(focus_label, placeholder="e.g. Summer Special OR Review text")
    
    st.write("") 
    
    # Conditional Button Label
    btn_label = "✨ Generate Post"
    if uploaded_file:
        btn_label = "✨ Generate Text (Using Uploaded Photo)"
        st.success(f"📸 Image Uploaded: {uploaded_file.name}. AI Image Gen will be skipped.")
        
    run_btn = st.button(btn_label, type="primary")

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
            headline = "Error"; body = "Error"; img_prompt = ""
            
            try:
                raw_output = generate_post_content(
                    site_text, focus_input, keyword_input, 
                    selected_model_name, temperature, 
                    post_type, vibe
                )
                headline = raw_output.split("HEADLINE:")[1].split("BODY:")[0].strip()
                body = raw_output.split("BODY:")[1].split("IMAGE_PROMPT:")[0].strip()
                img_prompt = raw_output.split("IMAGE_PROMPT:")[1].strip()
            except Exception as e:
                st.error(f"Text Gen Error: {e}")

            # 3. Image Logic (Skip if Uploaded)
            generated_image = None
            if uploaded_file:
                st.write("📂 Processing uploaded image...")
                # We don't need to do anything, just display it later
            else:
                if img_prompt and img_prompt != "Error":
                    st.write("📸 Generating image...")
                    generated_image = generate_image(img_prompt)
                else:
                    st.warning("Skipping Image Gen (No Prompt detected)")

            # 4. Save Temp (For AI Gen only)
            local_img_name = "temp_image.jpg"
            if generated_image:
                generated_image.save(local_img_name, include_generation_parameters=False)
            
            status.update(label="Complete!", state="complete", expanded=False)

            # --- RESULT DISPLAY ---
            with col2:
                st.subheader("3. Final Result")
                
                # CASE A: USER UPLOADED PHOTO
                if uploaded_file:
                    st.image(uploaded_file, caption="User Uploaded Photo")
                
                # CASE B: AI GENERATED PHOTO
                elif generated_image: 
                    st.image(local_img_name, caption="Generated by Imagen")
                    with open(local_img_name, "rb") as f:
                        st.download_button("⬇️ Download Image", f, "post_image.jpg", "image/jpeg")
                
                # CASE C: FAILED / BLOCKED
                elif not uploaded_file and not generated_image:
                    st.warning("Image Blocked (Safety Filter) or Generation Failed")

                st.divider()
                st.text_input("Headline", value=headline)
                st.text_area("Body", value=body, height=150)
                
                if not uploaded_file:
                    st.caption(f"Prompt Used: {img_prompt}")
