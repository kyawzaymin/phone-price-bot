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
    # Multi-engine OCR with direct image decoding
    try:
        url = "https://api.ocr.space/parse/image"
        payload = {
            "apikey": "K87899142388957",
            "language": "eng",
            "isTable": True,
            "OCREngine": 2,
            "scale": True,
            "detectOrientation": True
        }
        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, data=payload, files=files)
            res_json = resp.json()
            if res_json.get("ParsedResults"):
                parsed_text = res_json["ParsedResults"][0].get("ParsedText", "")
                if parsed_text:
                    return parse_price_text(parsed_text, supplier)
    except Exception as e:
        print(f"OCR Error: {e}")

    return []
