from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from simplification_model import universal_simplify

app = FastAPI()

# ---------------------------------------------------
# CORS FIX — allows frontend websites to call the API
# ---------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all domains
    allow_credentials=True,
    allow_methods=["*"],  # allow GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # allow all headers
)
# ---------------------------------------------------

class SimplifyRequest(BaseModel):
    text: str
    level: str

@app.post("/simplify")
def simplify_text(request: SimplifyRequest):
    simplified = universal_simplify(request.text, request.level)
    return {
        "input": request.text,
        "level": request.level,
        "simplified": simplified
    }

@app.get("/")
def root():
    return {"message": "API is running!"}
