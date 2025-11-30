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

# --- SIDEBAR: AUTH & VA INSTRUCTIONS ---
with st.sidebar:
    st.title("🔐 Agency Tools")
    
    # --- AUTHENTICATION ---
    auth_ready = False
    
    # Check for secrets (Local or Cloud)
    if "gcp_service_account" in st.secrets:
        try:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            project_id = st.secrets["gcp_service_account"]["project_id"]
            
            # Initialize Vertex AI
            vertexai.init(
                project=project_id, 
                location="us-central1", 
                credentials=creds
            )
            auth_ready = True
            st.success(f"✅ Connected: {project_id}")
            
        except Exception as e:
            st.error(f"Secrets Error: {e}")
    else:
        st.warning("⚠️ No Secrets found.")
        st.info("Paste TOML into App Settings > Secrets.")

    # --- VA CHECKLIST ---
    st.markdown("---")
    st.subheader("✅ VA Quality Checklist")
    st.info("""
    **Before posting, check these 3 things:**
    
    1. **The Image:** 
       - Is it realistic? 
       - Ensure there is NO gibberish text or logos. 
       - No weird fingers/faces.
       
    2. **The Text:**
       - Does it sound like a human receptionist?
       - If it says "Unleash" or "Elevate," **Re-run it.**
       - Is the phone number/link correct?
       
    3. **The SEO:**
       - Did it use the Target Keyword?
    """)

# --- HELPER FUNCTIONS ---

def get_website_text(url):
    """Scrapes the service page to understand what we are selling."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract meaningful text
        text = " ".join([p.get_text() for p in soup.find_all(['h1', 'h2', 'h3', 'p'])])
        return text[:5000].strip()
    except Exception as e:
        return None

def generate_post_content(text, focus_topic, keyword):
    """Uses Gemini 2.5 Flash to write the post with STRICT tone rules."""
    
    # Use the latest Flash model
    model = GenerativeModel("gemini-2.5-flash-001")
    
    # Dynamic keyword instruction
    keyword_instruction = ""
    if keyword:
        keyword_instruction = f"MANDATORY: You MUST include the exact phrase '{keyword}' naturally in the Headline or first sentence."
    
    prompt = f"""
    You are a helpful Front Desk Receptionist for a local medical/service business. 
    You are NOT a marketing copywriter. You are writing a Google Business Profile update.
    
    CONTEXT SOURCE: {text}
    FOCUS TOPIC: {focus_topic}
    TARGET KEYWORD: {keyword if keyword else "Extract main entity from text"}

    ---
    STRICT TONE GUIDELINES (DO NOT IGNORE):
    1. **Anti-Fluff Policy:** Do NOT use words like: "Unleash," "Elevate," "Transform," "Revolutionary," "Game-changer," "Dive into," "Realm," or "Magic."
    2. **Voice:** Be direct, warm, and factual. Use Grade 8 English. Simple sentences.
    3. **Google NLP:** Focus on the specific Entity (Service Name) and Location.
    4. {keyword_instruction}
    ---

    OUTPUT FORMAT:
    HEADLINE: [Direct, Keyword-Rich, under 10 words. Example: "Teeth Whitening in Austin"]
    BODY: [2-3 sentences max. State the problem, the solution, and the benefit. End with a clear Call to Action.]
    IMAGE_PROMPT: [Detailed prompt for an AI photographer. Describe a photorealistic, candid, high-end photo. Describe lighting (e.g. 'soft daylight') and camera style (e.g. 'shot on 35mm'). Do NOT describe text, logos, or cartoons.]
    """
    
    # Low temperature = Factual, boring (good for local SEO)
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.2}
    )
    return response.text

def generate_image(prompt):
    """Uses Imagen 3 to generate the photo."""
    
    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
    
    # Refine prompt for realism
    full_prompt = f"{prompt}, photorealistic, 4k resolution, highly detailed, professional photography, natural lighting, bokeh, 35mm lens, no text, no watermarks"
    
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
    
    # Split inputs for cleaner UI
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
                
                # Step 1: Read Website
                st.write("🕷️ Reading website content...")
                site_text = get_website_text(url_input)
                
                if not site_text or len(site_text) < 50:
                    status.update(label="Error reading website!", state="error")
                    st.error("Could not scrape text. Website might block bots. Try pasting text manually.")
                    st.stop()
                
                # Step 2: Gemini Writes
                st.write("🧠 Gemini 2.5 Flash is optimizing content...")
                try:
                    raw_output = generate_post_content(site_text, focus_input, keyword_input)
                except Exception as e:
                    status.update(label="Gemini Error", state="error")
                    st.error(f"Gemini API Error: {e}")
                    st.stop()
                
                # Step 3: Parse Logic
                try:
                    headline = raw_output.split("HEADLINE:")[1].split("BODY:")[0].strip()
                    body_part = raw_output.split("BODY:")[1]
                    body = body_part.split("IMAGE_PROMPT:")[0].strip()
                    img_prompt = raw_output.split("IMAGE_PROMPT:")[1].strip()
                except Exception as e:
                    headline = "Error Parsing Headline"
                    body = raw_output
                    img_prompt = f"Professional photo representing {focus_input}"
                
                # Step 4: Imagen Creates
                st.write("📸 Imagen 3 is taking the photo...")
                try:
                    generated_image = generate_image(img_prompt)
                    
                    # Convert to bytes for display
                    img_byte_arr = io.BytesIO()
                    generated_image.save(img_byte_arr, include_generation_parameters=False)
                    img_byte_arr.seek(0)
                    
                    status.update(label="Complete!", state="complete", expanded=False)
                    
                except Exception as e:
                    status.update(label="Image Generation Failed", state="error")
                    st.error(f"Imagen Error: {e}")
                    st.stop()

            # --- DISPLAY RESULTS IN COLUMN 2 ---
            with col2:
                st.subheader("2. Result")
                
                # Display Image
                st.image(img_byte_arr, use_column_width=True, caption="Generated by Imagen 3")
                
                # Download Button for Image
                st.download_button(
                    label="⬇️ Download Image",
                    data=img_byte_arr,
                    file_name="gbp_post_image.jpg",
                    mime="image/jpeg"
                )
                
                st.divider()
                
                # Display Text
                st.text_input("Headline (Post Title)", value=headline)
                st.text_area("Caption (Post Body)", value=body, height=150)
                
                st.caption(f"**AI Prompt Used:** {img_prompt}")

with st.expander("ℹ️ How to use this tool"):
    st.markdown("""
    1. **Paste URL:** Enter the client's specific service page.
    2. **Keyword:** Enter the EXACT phrase you want to rank for (e.g. "Implants near me").
    3. **Review:** Ensure the tone is helpful and direct, not "salesy."
    """)