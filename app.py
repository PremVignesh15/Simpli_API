from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
from typing import Optional

from sapling import SaplingClient  # Sapling grammar API

app = FastAPI(
    title="Text Simplification API",
    description="Multilingual text simplification (English, Hindi, Tamil, Telugu, Urdu) with Sapling grammar correction for English",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Load dictionaries ----------

def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

ENGLISH_SIMPLIFICATIONS = load_json("english_simplifications.json")
HINDI_SIMPLIFICATIONS   = load_json("hindi_simplifications.json")
TAMIL_SIMPLIFICATIONS   = load_json("tamil_simplifications.json")
TELUGU_SIMPLIFICATIONS  = load_json("telugu_simplifications.json")
URDU_SIMPLIFICATIONS    = load_json("urdu_simplifications.json")

print(f"Loaded English: {len(ENGLISH_SIMPLIFICATIONS)} words")
print(f"Loaded Hindi: {len(HINDI_SIMPLIFICATIONS)} words")
print(f"Loaded Tamil: {len(TAMIL_SIMPLIFICATIONS)} words")
print(f"Loaded Telugu: {len(TELUGU_SIMPLIFICATIONS)} words")
print(f"Loaded Urdu: {len(URDU_SIMPLIFICATIONS)} words")

# ---------- Simplification helpers ----------

def simplify_generic(text: str, mapping: dict, ignore_case: bool = True) -> str:
    """
    Replace words based on mapping.
    - For English (ignore_case=True): use regex with word boundaries
    - For Indic scripts (ignore_case=False): use plain string replacement (no \\b)
    """
    if not mapping:
        return text

    result = text
    
    if ignore_case:
        # English: use word boundaries with case-insensitive matching
        for hard, easy in mapping.items():
            pattern = re.compile(r'\b' + re.escape(hard) + r'\b', flags=re.IGNORECASE)
            result = pattern.sub(easy, result)
    else:
        # Indic scripts: plain string replacement (\\b doesn't work)
        for hard, easy in mapping.items():
            result = result.replace(hard, easy)
    
    return result

def simplify_english(text: str) -> str:
    return simplify_generic(text, ENGLISH_SIMPLIFICATIONS, ignore_case=True)

def simplify_hindi(text: str) -> str:
    return simplify_generic(text, HINDI_SIMPLIFICATIONS, ignore_case=False)

def simplify_tamil(text: str) -> str:
    return simplify_generic(text, TAMIL_SIMPLIFICATIONS, ignore_case=False)

def simplify_telugu(text: str) -> str:
    return simplify_generic(text, TELUGU_SIMPLIFICATIONS, ignore_case=False)

def simplify_urdu(text: str) -> str:
    return simplify_generic(text, URDU_SIMPLIFICATIONS, ignore_case=False)

def detect_language(text: str) -> str:
    """Detect language based on Unicode character ranges."""
    for ch in text:
        code = ord(ch)
        if 0x0900 <= code <= 0x097F:
            return "hindi"
        if 0x0B80 <= code <= 0x0BFF:
            return "tamil"
        if 0x0C00 <= code <= 0x0C7F:
            return "telugu"
        if 0x0600 <= code <= 0x06FF:
            return "urdu"
    return "english"

def universal_simplify(text: str, language: Optional[str] = None) -> str:
    """Route to appropriate simplification function based on language."""
    lang = (language or "auto").lower()

    if lang == "auto":
        lang = detect_language(text)

    if lang in ["english", "en"]:
        return simplify_english(text)
    if lang in ["hindi", "hi"]:
        return simplify_hindi(text)
    if lang in ["tamil", "ta"]:
        return simplify_tamil(text)
    if lang in ["telugu", "te"]:
        return simplify_telugu(text)
    if lang in ["urdu", "ur"]:
        return simplify_urdu(text)

    return simplify_english(text)

# ---------- Sapling grammar correction (English only) ----------

# WARNING: Do NOT commit a real key to a public repo.
SAPLING_API_KEY = "27L2C1YU2RMQ9UU4MMRUPAHEOMOTXJJO"

sapling_client = SaplingClient(api_key=SAPLING_API_KEY)
SAPLING_ENABLED = True

def postprocess_punctuation(text: str) -> str:
    """
    Optional custom punctuation rule, e.g. ensure a comma after 'kind ask'
    before 'shift to' if present.
    """
    pattern = re.compile(r'\b(kind ask)\s+(shift to)\b', flags=re.IGNORECASE)
    return pattern.sub(r'\1, \2', text)

def correct_grammar(text: str, language: str = "english") -> str:
    """
    Use Sapling to grammar-correct English text only.
    For other languages, return text unchanged.
    """
    if not text.strip():
        return text

    lang = (language or "english").lower()
    # Only run grammar correction for English
    if lang not in ["english", "en"]:
        return text

    if not SAPLING_ENABLED:
        return text

    try:
        edits = sapling_client.edits(text, session_id="simplify_session")
        corrected = text
        # Apply edits from end to start so indices remain valid
        for edit in sorted(edits, key=lambda e: e["start"], reverse=True):
            start = edit["start"]
            end = edit["end"]
            replacement = edit.get("replacement", "")
            corrected = corrected[:start] + replacement + corrected[end:]
        corrected = postprocess_punctuation(corrected)
        return corrected.strip()
    except Exception as e:
        print(f"Sapling error: {e}")
        return text

# ---------- Schemas ----------

class SimplifyRequest(BaseModel):
    text: str
    language: Optional[str] = "auto"

class SimplifyResponse(BaseModel):
    original: str
    simplified: str

# ---------- Endpoints ----------

@app.get("/")
def root():
    return {
        "message": "Text Simplification API with Sapling Grammar Correction",
        "status": "running",
        "version": "3.1.0",
        "sapling_enabled": SAPLING_ENABLED,
        "supported_languages": ["English", "Hindi", "Tamil", "Telugu", "Urdu"],
        "endpoints": {
            "simplify": "POST /simplify",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "dictionaries": {
            "english": len(ENGLISH_SIMPLIFICATIONS),
            "hindi": len(HINDI_SIMPLIFICATIONS),
            "tamil": len(TAMIL_SIMPLIFICATIONS),
            "telugu": len(TELUGU_SIMPLIFICATIONS),
            "urdu": len(URDU_SIMPLIFICATIONS)
        },
        "sapling_enabled": SAPLING_ENABLED
    }

@app.post("/simplify", response_model=SimplifyResponse)
def simplify_text(request: SimplifyRequest):
    if not request.text or request.text.strip() == "":
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    if len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")

    try:
        # Step 1: Simplify based on dictionary
        simplified_raw = universal_simplify(request.text, request.language)
        
        # Step 2: Grammar correction (English only)
        simplified_corrected = correct_grammar(simplified_raw, request.language)

        return SimplifyResponse(
            original=request.text,
            simplified=simplified_corrected
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simplification error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
