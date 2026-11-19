import os
import io
import re
import json
import unicodedata
from PIL import Image
import google.generativeai as genai

MY_DIGITS = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")

def clean_text(text):
    if not text:
        return ""
    return unicodedata.normalize("NFKC", str(text)).translate(MY_DIGITS)

def parse_price_text(text, supplier="Supplier"):
    cleaned = clean_text(text)
    lines = cleaned.split("\n")
    items = []
    
    current_section = "General"
    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        
        if any(sec in line_s.upper() for sec in ["CEIR", "OFFICIAL GLOBAL", "CHINA PI", "TABLET", "ACTIVATED"]):
            current_section = line_s
            continue
            
        m = re.search(r"([A-Za-z0-9\s\+\.\"\-]+?)(?:\(([0-9\+\/gbGBg]+)\))?\s*[:=]\s*([0-9\s,]+)", line_s)
        if m:
            raw_model = m.group(1).strip().strip("*").strip()
            ram_rom = m.group(2).strip() if m.group(2) else "Standard"
            price_str = re.sub(r"[^\d]", "", m.group(3))
            
            model = raw_model
            if model.startswith("N") and len(model) > 1 and model[1].isdigit():
                model = "Redmi Note " + model[1:]
            elif model.lower().startswith("rm"):
                model = "Redmi " + model[2:].strip()
            elif model.lower().startswith("a7"):
                model = "Xiaomi A7 " + model[2:].strip()
                
            is_oos = "ကုန်" in line_s
            price = int(price_str) if price_str else None
            
            items.append({
                "model": model,
                "ram_storage": ram_rom,
                "color": "Standard",
                "region": current_section,
                "price": price,
                "stock_status": "oos" if is_oos else "instock",
                "raw_text": line_s
            })
    return items

def parse_image_with_vision(image_bytes, supplier="Supplier"):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set.")
        return []
    
    try:
        genai.configure(api_key=api_key)
        # Use flash model for fast and accurate image OCR
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = (
            "Extract all phone/device models, RAM/storage, color, region/spec, and prices from this supplier price list image. "
            "Return ONLY a valid JSON object with key 'items' containing an array of objects. Each object must have: "
            "'model' (e.g. Redmi K100 Pro, Note 17, CIVI 3), 'ram_storage' (e.g. 12/256, 8/128, 4/64), "
            "'color' (e.g. Black, Blue, Coffee, Standard), 'region' (e.g. Global, Global Change, China PI, Activated), "
            "'price' (integer MMK price only, e.g. 2910000; null if missing), "
            "'stock_status' ('oos' if marked ကုန် or out of stock, otherwise 'instock')."
        )
        
        image = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([prompt, image])
        text_resp = response.text.strip()
        
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3].strip()
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3].strip()
            
        data = json.loads(text_resp)
        return data.get("items", [])
    except Exception as e:
        print(f"Error parsing image with Gemini: {e}")
        return []
