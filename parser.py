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
            
        p_match = re.search(r"(\d[\d\s,]{4,}\d|\d{5,})", line_s)
        if p_match:
            price_raw = re.sub(r"[^\d]", "", p_match.group(1))
            if len(price_raw) >= 5:
                before_price = line_s[:p_match.start()].strip().rstrip(":=|").strip()
                ram_match = re.search(r"\(?(\d{1,2}[\+\/]\d{2,3}(?:gb|GB|g|G)?)\)?", before_price)
                if ram_match:
                    ram_storage = ram_match.group(1)
                    model_part = before_price[:ram_match.start()].strip().strip("*").strip()
                    color_part = before_price[ram_match.end():].strip().lstrip(":=|,").strip()
                else:
                    ram_storage = "Standard"
                    model_part = before_price.strip("*").strip()
                    color_part = "Standard"
                    
                model = model_part
                if model.startswith("N") and len(model) > 1 and model[1].isdigit():
                    model = "Redmi Note " + model[1:]
                elif model.lower().startswith("rm"):
                    model = "Redmi " + model[2:].strip()
                elif model.lower().startswith("a7"):
                    model = "Xiaomi A7 " + model[2:].strip()
                elif not model:
                    model = "Phone Model"
                    
                items.append({
                    "model": model,
                    "ram_storage": ram_storage,
                    "color": color_part or "Standard",
                    "region": current_section,
                    "price": int(price_raw),
                    "stock_status": "oos" if "ကုန်" in line_s else "instock",
                    "raw_text": line_s
                })
    return items

def parse_image_with_vision(image_bytes, supplier="Supplier"):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set.")
        return []
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = (
            "You are an expert phone price list table parser. Examine this supplier price list image carefully. "
            "It has columns: [Model / Item Name] | [Color] | [Price in MMK]. "
            "Extract every single phone, tablet, and accessory row. "
            "Return ONLY a clean JSON object with this exact structure: "
            "{\"items\": [{\"model\": \"K100 Pro Max\", \"ram_storage\": \"12+256g\", \"color\": \"Blue\", \"region\": \"Activated\", \"price\": 3180000, \"stock_status\": \"instock\"}]}. "
            "Rules:\n"
            "1. 'price' must be an integer in MMK without commas (e.g. 3180000).\n"
            "2. If price is missing or blank, omit the item.\n"
            "3. If marked 'ကုန်', set 'stock_status': 'oos', otherwise 'instock'.\n"
            "4. Do NOT output markdown code blocks or extra text."
        )
        
        image = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([prompt, image])
        text_resp = response.text.strip()
        
        if "```" in text_resp:
            text_resp = re.sub(r"```json\s*", "", text_resp)
            text_resp = re.sub(r"```\s*", "", text_resp).strip()
            
        data = json.loads(text_resp)
        if isinstance(data, dict):
            return data.get("items", [])
        elif isinstance(data, list):
            return data
    except Exception as e:
        print(f"Gemini Vision parsing error: {e}")
        return []
