import sys
import os
import warnings
from dotenv import load_dotenv

# Ignore future warnings from deprecated package imports
warnings.filterwarnings("ignore", category=FutureWarning)

# Load env variables and fix pythonpath
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from anthropic import Anthropic
import google.generativeai as genai
from groq import Groq

def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            print(text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        except Exception:
            print(text.encode('ascii', errors='replace').decode('ascii'))

def check_claude():
    safe_print("--------------------------------------------------")
    safe_print("Checking Anthropic Claude...")
    if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY.startswith("dummy"):
        safe_print("[-] ANTHROPIC_API_KEY is not configured or is dummy.")
        return False
    try:
        headers = {}
        if settings.ANTHROPIC_WORKSPACE_ID:
            headers["anthropic-workspace-id"] = settings.ANTHROPIC_WORKSPACE_ID
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, default_headers=headers)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Ping"}]
        )
        safe_print(f"[+] Claude is WORKING. Response: {response.content[0].text.strip()}")
        return True
    except Exception as e:
        safe_print(f"[x] Claude FAILED: {e}")
        return False

def check_gemini():
    safe_print("--------------------------------------------------")
    safe_print("Checking Google Gemini...")
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.startswith("dummy"):
        safe_print("[-] GEMINI_API_KEY is not configured or is dummy.")
        return False
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name=settings.GEMINI_MODEL)
        response = model.generate_content("Ping")
        text = response.text.strip() if response.text else "Empty response"
        safe_print(f"[+] Gemini ({settings.GEMINI_MODEL}) is WORKING. Response: {text}")
        return True
    except Exception as e:
        safe_print(f"[x] Gemini ({settings.GEMINI_MODEL}) FAILED: {e}")
        return False

def check_groq():
    safe_print("--------------------------------------------------")
    safe_print("Checking Groq...")
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY.startswith("dummy"):
        safe_print("[-] GROQ_API_KEY is not configured or is dummy.")
        return False
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Ping"}]
        )
        safe_print(f"[+] Groq ({settings.GROQ_MODEL}) is WORKING. Response: {response.choices[0].message.content.strip()}")
        return True
    except Exception as e:
        safe_print(f"[x] Groq ({settings.GROQ_MODEL}) FAILED: {e}")
        return False

def main():
    safe_print("==================================================")
    safe_print("REVENUE RECOVERY PROVIDER STARTUP/DIAGNOSTIC CHECK")
    safe_print("==================================================")
    safe_print(f"Configured Gemini Model: {settings.GEMINI_MODEL}")
    safe_print(f"Configured Groq Model:   {settings.GROQ_MODEL}")
    safe_print("==================================================")
    
    claude_ok = check_claude()
    gemini_ok = check_gemini()
    groq_ok = check_groq()
    
    safe_print("==================================================")
    safe_print("SUMMARY:")
    safe_print(f"Claude: {'WORKING' if claude_ok else 'FAILED/NOT CONFIG'}")
    safe_print(f"Gemini: {'WORKING' if gemini_ok else 'FAILED/NOT CONFIG'}")
    safe_print(f"Groq:   {'WORKING' if groq_ok else 'FAILED/NOT CONFIG'}")
    safe_print("==================================================")

if __name__ == "__main__":
    main()
