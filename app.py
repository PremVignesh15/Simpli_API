from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import re
from typing import Optional
import os

# Initialize FastAPI app
app = FastAPI(
    title="Text Simplification API",
    description="Multilingual text simplification for accessibility (English & Hindi)",
    version="1.0.0"
)

# Enable CORS for mobile app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your mobile app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Load Dictionaries ----
def load_dict(filepath):
    """Load JSON dictionary file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Using empty dictionary.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: {filepath} is not valid JSON.")
        return {}

# Get dictionary directory path
DICT_DIR = os.path.join(os.path.dirname(__file__), "dictionaries")

# Load all dictionaries at startup (once)
ENGLISH_SIMPLIFICATIONS = load_dict(os.path.join(DICT_DIR, "english_simplifications.json"))
HINDI_SIMPLIFICATIONS = load_dict(os.path.join(DICT_DIR, "hindi_simplifications.json"))

print(f"Loaded {len(ENGLISH_SIMPLIFICATIONS)} English words")
print(f"Loaded {len(HINDI_SIMPLIFICATIONS)} Hindi words")

# ---- Request/Response Models ----
class SimplifyRequest(BaseModel):
    text: str
    language: Optional[str] = "auto"  # "auto", "en", "hi"

class SimplifyResponse(BaseModel):
    original: str
    simplified: str
    language_detected: str
    words_simplified: int

# ---- Simplification Functions ----
def detect_language(text: str) -> str:
    """Detect if text is Hindi, English, or Mixed"""
    has_hindi = any('\u0900' <= ch <= '\u097F' for ch in text)
    has_english = any(('A' <= ch <= 'Z') or ('a' <= ch <= 'z') for ch in text)
    
    if has_hindi and has_english:
        return "mixed"
    elif has_hindi:
        return "hindi"
    else:
        return "english"

def simplify_english(text: str, dictionary: dict) -> tuple[str, int]:
    """Simplify English text using dictionary"""
    count = 0
    for word, simple_word in dictionary.items():
        pattern = rf"\b{word}\b"
        if re.search(pattern, text, flags=re.IGNORECASE):
            text = re.sub(pattern, simple_word, text, flags=re.IGNORECASE)
            count += 1
    return text, count

def simplify_hindi(text: str, dictionary: dict) -> tuple[str, int]:
    """Simplify Hindi text using dictionary"""
    count = 0
    for word, simple_word in dictionary.items():
        pattern = rf"\b{word}\b"
        if re.search(pattern, text):
            text = re.sub(pattern, simple_word, text)
            count += 1
    return text, count

def simplify_mixed(text: str, en_dict: dict, hi_dict: dict) -> tuple[str, int]:
    """Simplify mixed Hindi-English text word-by-word"""
    words = text.split()
    simplified_words = []
    count = 0
    
    for word in words:
        # Remove punctuation for matching
        core_word = re.sub(r'[^\w\u0900-\u097F]', '', word)
        
        # Try English dictionary
        simple_en = en_dict.get(core_word.lower())
        # Try Hindi dictionary
        simple_hi = hi_dict.get(core_word)
        
        if simple_en:
            new_word = word.replace(core_word, simple_en)
            simplified_words.append(new_word)
            count += 1
        elif simple_hi:
            new_word = word.replace(core_word, simple_hi)
            simplified_words.append(new_word)
            count += 1
        else:
            simplified_words.append(word)
    
    return ' '.join(simplified_words), count

def universal_simplify(text: str, language: str = "auto") -> tuple[str, str, int]:
    """Main simplification function"""
    # Detect language if auto
    if language == "auto":
        detected_lang = detect_language(text)
    else:
        detected_lang = language
    
    # Simplify based on detected language
    if detected_lang == "mixed":
        simplified_text, count = simplify_mixed(text, ENGLISH_SIMPLIFICATIONS, HINDI_SIMPLIFICATIONS)
    elif detected_lang == "hindi":
        simplified_text, count = simplify_hindi(text, HINDI_SIMPLIFICATIONS)
    else:  # english
        simplified_text, count = simplify_english(text, ENGLISH_SIMPLIFICATIONS)
    
    return simplified_text, detected_lang, count

# ---- API Endpoints ----
@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "message": "Text Simplification API is running",
        "version": "1.0.0",
        "endpoints": {
            "simplify": "/simplify (POST)",
            "health": "/health (GET)",
            "docs": "/docs (Swagger UI)"
        }
    }

@app.get("/health")
def health_check():
    """Health check for monitoring"""
    return {
        "status": "healthy",
        "dictionaries_loaded": {
            "english": len(ENGLISH_SIMPLIFICATIONS),
            "hindi": len(HINDI_SIMPLIFICATIONS)
        }
    }

@app.post("/simplify", response_model=SimplifyResponse)
def simplify_text(request: SimplifyRequest):
    """
    Simplify text in English, Hindi, or mixed language
    
    Example request:
    {
        "text": "Please proceed to the verification counter immediately.",
        "language": "auto"
    }
    """
    if not request.text or request.text.strip() == "":
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    try:
        simplified, detected_lang, count = universal_simplify(request.text, request.language)
        
        return SimplifyResponse(
            original=request.text,
            simplified=simplified,
            language_detected=detected_lang,
            words_simplified=count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simplification error: {str(e)}")

@app.get("/stats")
def get_stats():
    """Get dictionary statistics"""
    return {
        "total_words": len(ENGLISH_SIMPLIFICATIONS) + len(HINDI_SIMPLIFICATIONS),
        "english_words": len(ENGLISH_SIMPLIFICATIONS),
        "hindi_words": len(HINDI_SIMPLIFICATIONS),
        "supported_languages": ["english", "hindi", "mixed"]
    }

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
