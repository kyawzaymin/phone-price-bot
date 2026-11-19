import os
import io
import re
import json
import base64
import unicodedata
from PIL import Image
import httpx

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
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        print("ERROR: GROQ_API_KEY is not configured.")
        return []
    
    try:
        # Resize image for optimal vision API processing
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        max_size = (1600, 1600)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        b64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            "You are a professional price list data extractor. "
            "Examine this mobile phone supplier price list image carefully. "
            "Extract every phone and tablet model row with its RAM/Storage, Color, and Price in Myanmar Kyat (MMK). "
            "Return ONLY a clean JSON array of objects inside an 'items' key, formatted as: "
            "{\"items\": [{\"model\": \"Redmi Note 17\", \"ram_storage\": \"8/128\", \"color\": \"Black\", \"region\": \"Activated\", \"price\": 1070000, \"stock_status\": \"instock\"}]}. "
            "Price must be an integer without commas. Set stock_status to 'oos' if marked 'ကုန်', else 'instock'."
        )
        
        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ]
                }
            ],
            "temperature": 0.1
        }
        
        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        res_json = resp.json()
        
        if "choices" in res_json:
            raw_content = res_json["choices"][0]["message"]["content"].strip()
            
            # Extract JSON block from markdown if present
            if "```" in raw_content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_content)
                if match:
                    raw_content = match.group(1).strip()
            
            data = json.loads(raw_content)
            if isinstance(data, dict):
                return data.get("items", [])
            elif isinstance(data, list):
                return data
        else:
            print("Groq API Error Response:", res_json)
            return []
    except Exception as e:
        print(f"Error during vision OCR processing: {e}")
        return []
