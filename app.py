from fastapi import FastAPI
from pydantic import BaseModel
from simplification_model import universal_simplify

app = FastAPI(
    title="Universal Text Simplification API",
    description="Simplifies English, Hindi, or mixed text based on difficulty level.",
    version="1.0.0"
)

class SimplifyRequest(BaseModel):
    text: str
    level: str  # "Easy" or "Hard"

@app.post("/simplify")
def simplify_text(request: SimplifyRequest):
    try:
        simplified = universal_simplify(request.text, request.level)
        return {
            "input": request.text,
            "level": request.level,
            "simplified": simplified
        }
    except Exception as e:
        print("🔥 INTERNAL ERROR:", e)
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.get("/")
def root():
    return {"message": "Text Simplification API running successfully!"}

