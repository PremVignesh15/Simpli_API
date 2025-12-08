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
    description="Multilingual text simplification for Deaf and low-literacy users (English & Hindi)",
    version="1.0.0"
)

# Enable CORS for mobile app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
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

# Load dictionaries at startup (only standard versions, no levels)
ENGLISH_SIMPLIFICATIONS = load_dict("english_simplifications.json")
HINDI_SIMPLIFICATIONS = load_dict("hindi_simplifications.json")

print(f"✅ Loaded {len(ENGLISH_SIMPLIFICATIONS)} English words")
print(f"✅ Loaded {len(HINDI_SIMPLIFICATIONS)} Hindi words")

# ---- Request/Response Models ----
class SimplifyRequest(BaseModel):
    text: str
    language: Optional[str] = "auto"  # "auto", "en", "hi", "mixed"

class SimplifyResponse(BaseModel):
    original: str
    simplified: str
    language_detected: str
    words_simplified: int

# ---- Language Detection ----
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

# ---- Simplification Functions ----
def simplify_english(text: str, dictionary: dict) -> tuple:
    """Simplify English text using dictionary"""
    count = 0
    simplified_text = text
    
    for word, simple_word in dictionary.items():
        pattern = rf"\b{word}\b"
        matches = re.findall(pattern, simplified_text, flags=re.IGNORECASE)
        if matches:
            simplified_text = re.sub(pattern, simple_word, simplified_text, flags=re.IGNORECASE)
            count += len(matches)
    
    return simplified_text, count

def simplify_hindi(text: str, dictionary: dict) -> tuple:
    """Simplify Hindi text using dictionary"""
    count = 0
    simplified_text = text
    
    for word, simple_word in dictionary.items():
        pattern = rf"\b{word}\b"
        matches = re.findall(pattern, simplified_text)
        if matches:
            simplified_text = re.sub(pattern, simple_word, simplified_text)
            count += len(matches)
    
    return simplified_text, count

def simplify_mixed(text: str, en_dict: dict, hi_dict: dict) -> tuple:
    """Simplify mixed Hindi-English text word-by-word"""
    words = text.split()
    simplified_words = []
    count = 0
    
    for word in words:
        # Extract core word (remove punctuation)
        core_word = re.sub(r'[^\w\u0900-\u097F]', '', word)
        
        # Try English dictionary (lowercase)
        simple_en = en_dict.get(core_word.lower())
        # Try Hindi dictionary (as-is)
        simple_hi = hi_dict.get(core_word)
        
        if simple_en:
            new_word = word.replace(core_word, simple_en, 1)
            simplified_words.append(new_word)
            count += 1
        elif simple_hi:
            new_word = word.replace(core_word, simple_hi, 1)
            simplified_words.append(new_word)
            count += 1
        else:
            simplified_words.append(word)
    
    return ' '.join(simplified_words), count

def universal_simplify(text: str, language: str = "auto") -> tuple:
    """Main simplification function - detects language and simplifies"""
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
    """Root endpoint - API information"""
    return {
        "message": "Text Simplification API for Accessibility",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "simplify": "POST /simplify - Simplify text",
            "health": "GET /health - Health check",
            "stats": "GET /stats - Dictionary statistics",
            "docs": "GET /docs - Interactive API documentation"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "dictionaries_loaded": {
            "english": len(ENGLISH_SIMPLIFICATIONS),
            "hindi": len(HINDI_SIMPLIFICATIONS),
            "total": len(ENGLISH_SIMPLIFICATIONS) + len(HINDI_SIMPLIFICATIONS)
        }
    }

@app.post("/simplify", response_model=SimplifyResponse)
def simplify_text(request: SimplifyRequest):
    """
    Simplify text in English, Hindi, or mixed language
    
    Request Body:
    {
        "text": "Please proceed to the verification counter immediately.",
        "language": "auto"
    }
    
    Response:
    {
        "original": "Please proceed to the verification counter immediately.",
        "simplified": "Please go to the checking desk now.",
        "language_detected": "english",
        "words_simplified": 3
    }
    """
    # Validate input
    if not request.text or request.text.strip() == "":
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(request.text) > 10000:
        raise HTTPException(status_code=400, detail="Text too long (max 10,000 characters)")
    
    try:
        # Simplify text
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
        "languages": {
            "english": {
                "word_count": len(ENGLISH_SIMPLIFICATIONS),
                "sample_words": list(ENGLISH_SIMPLIFICATIONS.keys())[:5]
            },
            "hindi": {
                "word_count": len(HINDI_SIMPLIFICATIONS),
                "sample_words": list(HINDI_SIMPLIFICATIONS.keys())[:5]
            }
        },
        "supported_languages": ["english", "hindi", "mixed"]
    }

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
