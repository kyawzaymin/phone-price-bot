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
        print("ERROR: GROQ_API_KEY is not configured in Railway Variables.")
        return []
    
    try:
        # Resize image for fast and reliable API transmission
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        b64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            "You are an expert OCR parser for mobile phone price lists. "
            "Extract all phone/tablet rows from this price list image. "
            "Output each item on a separate line in this exact format: "
            "Model | RAM_Storage | Color | Price | StockStatus\n"
            "Example: Note 17 5G | 8/128GB | Black/Green/Violet | 1070000 | instock\n"
            "If out of stock or marked 'ကုန်', write 'oos' for StockStatus. Price must be numbers only. Do not add explanations."
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
            "temperature": 0.1,
            "max_tokens": 2048
        }
        
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            res_json = resp.json()
            
        if "choices" in res_json:
            text_out = res_json["choices"][0]["message"]["content"].strip()
            items = []
            
            for line in text_out.split("\n"):
                line_s = line.strip()
                if not line_s or "|" not in line_s:
                    continue
                parts = [p.strip() for p in line_s.split("|")]
                if len(parts) >= 4:
                    raw_model = parts[0]
                    ram_rom = parts[1] if len(parts) > 1 else "Standard"
                    color = parts[2] if len(parts) > 2 else "Standard"
                    price_digits = re.sub(r"[^\d]", "", parts[3])
                    status = parts[4].lower() if len(parts) > 4 else "instock"
                    
                    if not price_digits:
                        continue
                        
                    model = raw_model
                    if model.startswith("N") and len(model) > 1 and model[1].isdigit():
                        model = "Redmi Note " + model[1:]
                    elif model.lower().startswith("rm"):
                        model = "Redmi " + model[2:].strip()
                        
                    items.append({
                        "model": model,
                        "ram_storage": ram_rom,
                        "color": color,
                        "region": "Activated",
                        "price": int(price_digits),
                        "stock_status": "oos" if "oos" in status else "instock",
                        "raw_text": line_s
                    })
            return items
        else:
            print("Groq API Error Response:", res_json)
            return []
    except Exception as e:
        print(f"Vision OCR Exception: {e}")
        return []
