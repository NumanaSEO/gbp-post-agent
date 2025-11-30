import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account
import requests
from bs4 import BeautifulSoup
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Agency Post Factory",
    page_icon="🏥",
    layout="wide"
)

# --- CSS FOR CLEAN LOOK ---
st.markdown("""
    <style>
    .stButton>button {width: 100%; border-radius: 5px; height: 3em; font-weight: bold;}
    div[data-testid="stStatusWidget"] {border: 1px solid #ddd; border-radius: 10px; padding: 10px;}
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR: CONFIGURATION ---
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # 1. AUTHENTICATION
    st.subheader("1. Authentication")
    auth_ready = False
    if "gcp_service_account" in st.secrets:
        try:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            project_id = st.secrets["gcp_service_account"]["project_id"]
            vertexai.init(project=project_id, location="us-central1", credentials=creds)
            auth_ready = True
            st.success(f"Connected: {project_id}")
        except Exception as e:
            st.error(f"Secrets Error: {e}")
    else:
        st.warning("⚠️ No Secrets found.")

    # 2. AI MODEL CONFIG (NEW!)
    if auth_ready:
        st.divider()
        st.subheader("2. AI Model Config")
        
        # The Picker - Matches your screenshot options
        selected_model_name = st.selectbox(
            "Select Text Model",
            options=[
                "gemini-1.5-flash-001",   # The current Stable Workhorse
                "gemini-2.0-flash-exp",   # The new Experimental Flash
                "gemini-1.5-pro-001",     # Higher IQ, slower
            ],
            index=0, # Defaults to 1.5 Flash (Safe bet)
            help="If one model gives a 404 error, switch to another."
        )
        
        # Optional: Strictness Slider
        temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.2, help="Lower = More Factual. Higher = More Creative.")

    # 3. VA CHECKLIST
    st.divider()
    st.info("""
    **VA Checklist:**
    1. **Image:** No text/logos? Realistic?
    2. **Tone:** No "Unleash" or "Elevate"?
    3. **SEO:** Keyword included?
    """)

# --- HELPER FUNCTIONS ---

def get_website_text(url):
    """Scrapes the service page."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        text = " ".join([p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])])
        return text[:5000].strip()
    except Exception as e:
        return None

def generate_post_content(text, focus_topic, keyword, model_name, temp):
    """Uses the SELECTED Gemini model to write the post."""
    
    # We now use the model_name passed from the sidebar picker
    model = GenerativeModel(model_name)
    
    keyword_instruction = ""
    if keyword:
        keyword_instruction = f"MANDATORY: You MUST include the exact phrase '{keyword}' naturally in the Headline or first sentence."
    
    prompt = f"""
    You are a helpful Front Desk Receptionist for a local medical/service business. 
    
    CONTEXT SOURCE: {text}
    FOCUS TOPIC: {focus_topic}
    TARGET KEYWORD: {keyword if keyword else "Extract main entity from text"}

    ---
    STRICT TONE GUIDELINES:
    1. **Anti-Fluff:** No words like: "Unleash," "Elevate," "Transform," "Revolutionary," "Magic."
    2. **Voice:** Direct, warm, factual. Grade 8 English.
    3. **Google NLP:** Focus on the specific Service Name and Location.
    4. {keyword_instruction}
    ---

    OUTPUT FORMAT:
    HEADLINE: [Direct, Keyword-Rich, under 10 words]
    BODY: [2-3 sentences max. Problem -> Solution -> Call to Action.]
    IMAGE_PROMPT: [Photorealistic, candid, high-end photo. Describe lighting and camera style. NO TEXT/LOGOS.]
    """
    
    # Use the temperature from the sidebar slider
    response = model.generate_content(
        prompt,
        generation_config={"temperature": temp}
    )
    return response.text

def generate_image(prompt):
    """Uses Imagen 3."""
    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
    full_prompt = f"{prompt}, photorealistic, 4k, professional photography, natural lighting, bokeh, 35mm lens, no text"
    
    images = model.generate_images(
        prompt=full_prompt,
        number_of_images=1,
        language="en",
        aspect_ratio="4:3", 
        person_generation="allow_adult",
    )
    return images[0]

# --- MAIN UI ---

st.title("🏥 SEO Post Factory")
st.markdown("Generate **Entity-Optimized Content** from a URL.")
st.divider()

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("1. Input")
    url_input = st.text_input("Service Page URL", placeholder="https://client.com/teeth-whitening")
    
    sub_col1, sub_col2 = st.columns(2)
    with sub_col1:
        keyword_input = st.text_input("Target Keyword (SEO)", placeholder="e.g. Dentist in Austin")
    with sub_col2:
        focus_input = st.text_input("Focus/Offer (Optional)", placeholder="e.g. New Patient Special")
    
    run_btn = st.button("✨ Generate Post", type="primary")

    if run_btn:
        if not auth_ready:
            st.error("⚠️ Authentication missing. Check sidebar.")
        elif not url_input:
            st.warning("Please enter a URL.")
        else:
            with st.status("Agent is working...", expanded=True) as status:
                
                # Step 1: Scrape
                st.write("🕷️ Reading website content...")
                site_text = get_website_text(url_input)
                
                if not site_text or len(site_text) < 50:
                    status.update(label="Error reading website!", state="error")
                    st.error("Could not scrape text. Try pasting text manually.")
                    st.stop()
                
                # Step 2: Gemini Writes (Using Selected Model)
                st.write(f"🧠 {selected_model_name} is optimizing content...")
                try:
                    # PASS THE MODEL NAME AND TEMP HERE
                    raw_output = generate_post_content(site_text, focus_input, keyword_input, selected_model_name, temperature)
                except Exception as e:
                    status.update(label="Gemini Error", state="error")
                    st.error(f"Error with model {selected_model_name}: {e}")
                    st.info("Try selecting a different model in the Sidebar!")
                    st.stop()
                
                # Step 3: Parse
                try:
                    headline = raw_output.split("HEADLINE:")[1].split("BODY:")[0].strip()
                    body_part = raw_output.split("BODY:")[1]
                    body = body_part.split("IMAGE_PROMPT:")[0].strip()
                    img_prompt = raw_output.split("IMAGE_PROMPT:")[1].strip()
                except Exception as e:
                    headline = "Error Parsing Headline"
                    body = raw_output
                    img_prompt = f"Professional photo representing {focus_input}"
                
                # Step 4: Imagen
                st.write("📸 Imagen 3 is taking the photo...")
                try:
                    generated_image = generate_image(img_prompt)
                    img_byte_arr = io.BytesIO()
                    generated_image.save(img_byte_arr, include_generation_parameters=False)
                    img_byte_arr.seek(0)
                    status.update(label="Complete!", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="Image Generation Failed", state="error")
                    st.error(f"Imagen Error: {e}")
                    st.stop()

            # --- RESULT DISPLAY ---
            with col2:
                st.subheader("2. Result")
                st.image(img_byte_arr, use_column_width=True, caption="Generated by Imagen 3")
                
                st.download_button(
                    label="⬇️ Download Image",
                    data=img_byte_arr,
                    file_name="gbp_post_image.jpg",
                    mime="image/jpeg"
                )
                
                st.divider()
                st.text_input("Headline", value=headline)
                st.text_area("Caption", value=body, height=150)
                st.caption(f"**Model Used:** {selected_model_name} | **Prompt:** {img_prompt}")
