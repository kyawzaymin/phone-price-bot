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
            
        m = re.search(r"([A-Za-z0-9\s\+\.\"\-]+?)(?:\(([0-9\+\/gbGBg]+)\))?\s*[:=\|]?\s*([0-9\s,]+)", line_s)
        if m:
            raw_model = m.group(1).strip().strip("*").strip()
            ram_rom = m.group(2).strip() if m.group(2) else "Standard"
            price_str = re.sub(r"[^\d]", "", m.group(3))
            
            if not price_str or len(price_str) < 5:
                continue
                
            model = raw_model
            if model.startswith("N") and len(model) > 1 and model[1].isdigit():
                model = "Redmi Note " + model[1:]
            elif model.lower().startswith("rm"):
                model = "Redmi " + model[2:].strip()
            elif model.lower().startswith("a7"):
                model = "Xiaomi A7 " + model[2:].strip()
                
            is_oos = "ကုန်" in line_s
            items.append({
                "model": model,
                "ram_storage": ram_rom,
                "color": "Standard",
                "region": current_section,
                "price": int(price_str),
                "stock_status": "oos" if is_oos else "instock",
                "raw_text": line_s
            })
    return items

def parse_image_with_vision(image_bytes, supplier="Supplier"):
    # 1. First priority: Groq Vision API
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            # Resize appropriately
            img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8").replace("\n", "").strip()
            
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            prompt = (
                "You are an expert OCR price list reader. Extract all phone model rows from this supplier image. "
                "Output each item on its own line strictly in this format: "
                "Model | RAM_Storage | Color | Price | StockStatus\n"
                "Example: Note 17 5G | 8/128GB | Black/Green | 1070000 | instock\n"
                "Extract as many rows as possible. Price must be numbers only. If out of stock, write oos for StockStatus."
            )
            payload = {
                "model": "llama-3.2-11b-vision-preview",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_str}"}}
                        ]
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2048
            }
            with httpx.Client(timeout=45.0) as client:
                r = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                rj = r.json()
                if "choices" in rj:
                    content = rj["choices"][0]["message"]["content"]
                    items = []
                    for line in content.split("\n"):
                        if "|" in line:
                            pts = [p.strip() for p in line.split("|")]
                            if len(pts) >= 4:
                                p_num = re.sub(r"[^\d]", "", pts[3])
                                if p_num and len(p_num) >= 5:
                                    m_name = pts[0]
                                    if m_name.startswith("N") and len(m_name) > 1 and m_name[1].isdigit():
                                        m_name = "Redmi Note " + m_name[1:]
                                    elif m_name.lower().startswith("rm"):
                                        m_name = "Redmi " + m_name[2:].strip()
                                    items.append({
                                        "model": m_name,
                                        "ram_storage": pts[1] if len(pts) > 1 else "Standard",
                                        "color": pts[2] if len(pts) > 2 else "Standard",
                                        "region": "Activated",
                                        "price": int(p_num),
                                        "stock_status": "oos" if "oos" in pts[-1].lower() else "instock",
                                        "raw_text": line
                                    })
                    if items:
                        return items
        except Exception as e:
            print(f"Groq API Error: {e}")

    # 2. Universal Free OCR Fallback
    try:
        url = "https://api.ocr.space/parse/image"
        payload = {"isOverlayRequired": False, "apikey": "K87899142388957", "language": "eng", "isTable": True, "OCREngine": 2}
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, data=payload, files=files)
            res_json = resp.json()
            if res_json.get("ParsedResults"):
                parsed_text = res_json["ParsedResults"][0].get("ParsedText", "")
                if parsed_text:
                    return parse_price_text(parsed_text, supplier)
    except Exception as e:
        print(f"Fallback OCR Error: {e}")

    return []
