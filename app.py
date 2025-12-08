from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
from typing import Optional

app = FastAPI(
    title="Text Simplification API",
    description="Multilingual text simplification (English, Hindi, Tamil, Urdu)",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Load Dictionaries ----------

def load_dict(filepath: str) -> dict:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {filepath} not found, using empty dictionary.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: {filepath} is not valid JSON, using empty dictionary.")
        return {}

ENGLISH_SIMPLIFICATIONS = load_dict("english_simplifications.json")
HINDI_SIMPLIFICATIONS   = load_dict("hindi_simplifications.json")
TAMIL_SIMPLIFICATIONS   = load_dict("tamil_simplifications.json")
URDU_SIMPLIFICATIONS    = load_dict("urdu_simplifications.json")

print(f"English words: {len(ENGLISH_SIMPLIFICATIONS)}")
print(f"Hindi words  : {len(HINDI_SIMPLIFICATIONS)}")
print(f"Tamil words  : {len(TAMIL_SIMPLIFICATIONS)}")
print(f"Urdu words   : {len(URDU_SIMPLIFICATIONS)}")

# ---------- Models ----------

class SimplifyRequest(BaseModel):
    text: str
    # auto / english / hindi / tamil / urdu / mixed
    language: Optional[str] = "auto"

class SimplifyResponse(BaseModel):
    original: str
    simplified: str

# ---------- Language detection helpers ----------

def has_hindi(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)

def has_tamil(text: str) -> bool:
    return any("\u0B80" <= ch <= "\u0BFF" for ch in text)

def has_urdu(text: str) -> bool:
    # Urdu in Arabic script – main range
    return any("\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F" for ch in text)

def has_english(text: str) -> bool:
    return any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)

def detect_language(text: str) -> str:
    h = has_hindi(text)
    t = has_tamil(text)
    u = has_urdu(text)
    e = has_english(text)

    langs = [h, t, u, e].count(True)

    if langs > 1:
        return "mixed"
    if h:
        return "hindi"
    if t:
        return "tamil"
    if u:
        return "urdu"
    return "english"  # default fallback

# ---------- Simplification primitives ----------

def simplify_generic(text: str, dictionary: dict, ignore_case: bool = False) -> str:
    simplified = text
    if ignore_case:
        for word, simple in dictionary.items():
            pattern = rf"\b{re.escape(word)}\b"
            simplified = re.sub(pattern, simple, simplified, flags=re.IGNORECASE)
    else:
        for word, simple in dictionary.items():
            pattern = rf"\b{re.escape(word)}\b"
            simplified = re.sub(pattern, simple, simplified)
    return simplified

def simplify_english(text: str) -> str:
    return simplify_generic(text, ENGLISH_SIMPLIFICATIONS, ignore_case=True)

def simplify_hindi(text: str) -> str:
    return simplify_generic(text, HINDI_SIMPLIFICATIONS, ignore_case=False)

def simplify_tamil(text: str) -> str:
    return simplify_generic(text, TAMIL_SIMPLIFICATIONS, ignore_case=False)

def simplify_urdu(text: str) -> str:
    return simplify_generic(text, URDU_SIMPLIFICATIONS, ignore_case=False)

def simplify_mixed(text: str) -> str:
    """
    Very simple mixed handling:
    - split by spaces
    - for each token, try English, then Hindi, then Tamil, then Urdu
    """
    words = text.split()
    out = []

    for word in words:
        core = re.sub(r"[^\w\u0900-\u097F\u0B80-\u0BFF\u0600-\u06FF]", "", word)

        replaced = word
        done = False

        if core:
            # English
            simple_en = ENGLISH_SIMPLIFICATIONS.get(core.lower())
            if simple_en:
                replaced = word.replace(core, simple_en, 1)
                done = True

            # Hindi
            if not done:
                simple_hi = HINDI_SIMPLIFICATIONS.get(core)
                if simple_hi:
                    replaced = word.replace(core, simple_hi, 1)
                    done = True

            # Tamil
            if not done:
                simple_ta = TAMIL_SIMPLIFICATIONS.get(core)
                if simple_ta:
                    replaced = word.replace(core, simple_ta, 1)
                    done = True

            # Urdu
            if not done:
                simple_ur = URDU_SIMPLIFICATIONS.get(core)
                if simple_ur:
                    replaced = word.replace(core, simple_ur, 1)
                    done = True

        out.append(replaced)

    return " ".join(out)

def universal_simplify(text: str, language: str = "auto") -> str:
    lang = detect_language(text) if language == "auto" else language.lower()

    if lang == "mixed":
        return simplify_mixed(text)
    if lang in ("en", "english"):
        return simplify_english(text)
    if lang in ("hi", "hindi"):
        return simplify_hindi(text)
    if lang in ("ta", "tamil"):
        return simplify_tamil(text)
    if lang in ("ur", "urdu"):
        return simplify_urdu(text)
    # fallback
    return simplify_english(text)

# ---------- Endpoints ----------

@app.get("/")
def root():
    return {
        "message": "Text Simplification API",
        "status": "running",
        "version": "2.0.0"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "dictionaries": {
            "english": len(ENGLISH_SIMPLIFICATIONS),
            "hindi": len(HINDI_SIMPLIFICATIONS),
            "tamil": len(TAMIL_SIMPLIFICATIONS),
            "urdu": len(URDU_SIMPLIFICATIONS)
        }
    }

@app.post("/simplify", response_model=SimplifyResponse)
def simplify_text(req: SimplifyRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    if len(req.text) > 10000:
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")

    try:
        simplified = universal_simplify(req.text, req.language)
        return SimplifyResponse(original=req.text, simplified=simplified)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simplification error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
