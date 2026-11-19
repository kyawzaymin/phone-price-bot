import os
import json
import google.generativeai as genai
from PIL import Image
import io

def parse_image_with_vision(image_bytes, supplier="Supplier"):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = (
        "Extract all phone/device models, RAM/storage, color, region/spec, and prices from this supplier price list image. "
        "Return ONLY a valid JSON object with key 'items' containing an array of objects. Each object must have: "
        "'model' (e.g. Redmi K100 Pro, Note 17, CIVI 3), 'ram_storage' (e.g. 12/256, 8/128, 4/64), "
        "'color' (e.g. Black, Blue, Coffee, Standard), 'region' (e.g. Global, Global Change, China PI, Activated), "
        "'price' (integer MMK price only, e.g. 2910000; null if missing), "
        "'stock_status' ('oos' if marked ကုန် or out of stock, otherwise 'instock')."
    )
    
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([prompt, image])
        text_resp = response.text.strip()
        
        # Clean markdown codeblocks
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3].strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3].strip()
            
        data = json.loads(text_resp)
        return data.get("items", [])
    except Exception as e:
        print(f"Error parsing image with Gemini: {e}")
        return []
