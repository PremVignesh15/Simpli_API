from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
from typing import Optional

app = FastAPI(
    title="Text Simplification API",
    description="Multilingual text simplification for Deaf and low-literacy users (English & Hindi)",
    version="1.0.0"
)

# CORS (allow all for now; restrict in production)
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
HINDI_SIMPLIFICATIONS = load_dict("hindi_simplifications.json")

print(f"Loaded {len(ENGLISH_SIMPLIFICATIONS)} English words")
print(f"Loaded {len(HINDI_SIMPLIFICATIONS)} Hindi words")

# ---------- Models ----------

class SimplifyRequest(BaseModel):
    text: str
    language: Optional[str] = "auto"  # "auto", "english", "hindi", "mixed"

class SimplifyResponse(BaseModel):
    original: str
    simplified: str

# ---------- Core Logic ----------

def detect_language(text: str) -> str:
    has_hindi = any("\u0900" <= ch <= "\u097F" for ch in text)
    has_english = any("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)
    if has_hindi and has_english:
        return "mixed"
    elif has_hindi:
        return "hindi"
    else:
        return "english"

def simplify_english(text: str, dictionary: dict) -> str:
    simplified_text = text
    for word, simple_word in dictionary.items():
        pattern = rf"\b{word}\b"
        simplified_text = re.sub(pattern, simple_word, simplified_text, flags=re.IGNORECASE)
    return simplified_text

def simplify_hindi(text: str, dictionary: dict) -> str:
    simplified_text = text
    for word, simple_word in dictionary.items():
        pattern = rf"\b{word}\b"
        simplified_text = re.sub(pattern, simple_word, simplified_text)
    return simplified_text

def simplify_mixed(text: str, en_dict: dict, hi_dict: dict) -> str:
    words = text.split()
    simplified_words = []

    for word in words:
        core = re.sub(r"[^\w\u0900-\u097F]", "", word)
        simple_en = en_dict.get(core.lower())
        simple_hi = hi_dict.get(core)

        if simple_en:
            simplified_words.append(word.replace(core, simple_en, 1))
        elif simple_hi:
            simplified_words.append(word.replace(core, simple_hi, 1))
        else:
            simplified_words.append(word)

    return " ".join(simplified_words)

def universal_simplify(text: str, language: str = "auto") -> str:
    detected = detect_language(text) if language == "auto" else language

    if detected == "mixed":
        return simplify_mixed(text, ENGLISH_SIMPLIFICATIONS, HINDI_SIMPLIFICATIONS)
    elif detected == "hindi":
        return simplify_hindi(text, HINDI_SIMPLIFICATIONS)
    else:
        return simplify_english(text, ENGLISH_SIMPLIFICATIONS)

# ---------- Endpoints ----------

@app.get("/")
def root():
    return {
        "message": "Text Simplification API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "english_words": len(ENGLISH_SIMPLIFICATIONS),
        "hindi_words": len(HINDI_SIMPLIFICATIONS)
    }

@app.post("/simplify", response_model=SimplifyResponse)
def simplify_text(request: SimplifyRequest):
    if not request.text or request.text.strip() == "":
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    if len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")

    try:
        simplified = universal_simplify(request.text, request.language)
        return SimplifyResponse(
            original=request.text,
            simplified=simplified
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simplification error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
