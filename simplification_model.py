import os
import re
import json
import time
import nltk
from nltk.tokenize import sent_tokenize

# Download NLTK Punkt only if needed
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# ---- Path Setup ----

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
INPUT_DIR = r"D:\Project\simpli3\input"
OUTPUT_DIR = r"D:\Project\simpli3\output"

DICT_DIR = os.path.dirname(__file__)

# ---- Load Dictionaries from JSON ----

def load_dict(filename):
    with open(os.path.join(DICT_DIR, filename), 'r', encoding='utf-8') as f:
        return json.load(f)

ENGLISH_SIMPLIFICATIONS = load_dict('english_simplifications.json')
ENGLISH_SIMPLIFICATIONS_BASIC = load_dict('english_simplifications_basic.json')
HINDI_SIMPLIFICATIONS = load_dict('hindi_simplifications.json')
HINDI_SIMPLIFICATIONS_BASIC = load_dict('hindi_simplifications_basic.json')

LEVELS = ["Hard", "Easy"]

# ---- Simplification Functions ----

def simplify_english_sentence(sentence: str, dictionary: dict) -> str:
    for word, simple_word in dictionary.items():
        sentence = re.sub(rf"\b{word}\b", simple_word, sentence, flags=re.IGNORECASE)
    return sentence

def simplify_hindi_sentence(sentence: str, dictionary: dict) -> str:
    for word, simple_word in dictionary.items():
        sentence = re.sub(rf"\b{word}\b", simple_word, sentence)
    return sentence

def simplify_mixed_sentence(sentence: str, en_dict: dict, hi_dict: dict) -> str:
    words = sentence.split()
    simplified_words = []
    for word in words:
        core_word = re.sub(r'[^\w\u0900-\u097F]', '', word)
        simple_en = en_dict.get(core_word.lower())
        simple_hi = hi_dict.get(core_word)
        if simple_en:
            new_word = word.replace(core_word, simple_en)
        elif simple_hi:
            new_word = word.replace(core_word, simple_hi)
        else:
            new_word = word
        simplified_words.append(new_word)
    return ' '.join(simplified_words)

def simplify_text_pure(text: str, level: str) -> str:
    def is_hindi(txt): return any('\u0900' <= ch <= '\u097F' for ch in txt)
    if is_hindi(text):
        hi_dict = HINDI_SIMPLIFICATIONS_BASIC if level == "Easy" else HINDI_SIMPLIFICATIONS
        sentences = re.split(r'[।.!?]', text)
        simplified = [simplify_hindi_sentence(s, hi_dict) for s in sentences if s.strip()]
        return '। '.join(simplified)
    else:
        en_dict = ENGLISH_SIMPLIFICATIONS_BASIC if level == "Easy" else ENGLISH_SIMPLIFICATIONS
        sentences = sent_tokenize(text)
        simplified = [simplify_english_sentence(s, en_dict) for s in sentences]
        return ' '.join(simplified)

def simplify_text_mixed(text, level):
    en_dict = ENGLISH_SIMPLIFICATIONS_BASIC if level == "Easy" else ENGLISH_SIMPLIFICATIONS
    hi_dict = HINDI_SIMPLIFICATIONS_BASIC if level == "Easy" else HINDI_SIMPLIFICATIONS
    lines = text.split('\n')
    simplified = [simplify_mixed_sentence(line, en_dict, hi_dict) for line in lines if line.strip()]
    return '\n'.join(simplified)

def universal_simplify(text: str, level: str) -> str:
    has_hindi = any('\u0900' <= ch <= '\u097F' for ch in text)
    has_english = any(('A' <= ch <= 'Z') or ('a' <= ch <= 'z') for ch in text)
    if has_hindi and has_english:
        return simplify_text_mixed(text, level)
    elif has_hindi:
        return simplify_text_pure(text, level)      # Hindi
    else:
        return simplify_text_pure(text, level)      # English

# ---- Input/Output Handling ----

def process_file(input_path, output_path, level):
    with open(input_path, 'r', encoding='utf-8') as infile:
        text = infile.read()
    simple_text = universal_simplify(text, level)
    with open(output_path, 'w', encoding='utf-8') as outfile:
        outfile.write(simple_text)
    try:
        os.remove(input_path)
        print(f"Input file '{input_path}' deleted after processing.")
    except Exception as e:
        print(f"Failed to delete input file '{input_path}': {e}")

if __name__ == "__main__":
    filename = "sample.txt"
    print("Select Simplification Level:")
    print("1. Hard (advanced words)")
    print("2. Easy (basic/simple words)")
    selected = input("Enter the number of your simplification level: ")
    try:
        selected_idx = int(selected) - 1
        user_level = LEVELS[selected_idx]
    except (ValueError, IndexError):
        print("Invalid input, defaulting to Easy.")
        user_level = "Easy"
    input_path = os.path.join(INPUT_DIR, filename)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_filename = f"output_{timestamp}_{user_level}.txt"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    process_file(input_path, output_path, level=user_level)
    print(f"Simplification complete for '{user_level}'. Check: {output_path}")
