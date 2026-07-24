import sys
import os
import time
import subprocess
import shutil
import re
import logging
from pathlib import Path

# Force stdout/stderr to use UTF-8 to prevent charmap UnicodeEncodeErrors in Windows background tasks
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-8s │ %(message)s")
logger = logging.getLogger("pinterest_agent.watchdog")

def get_gemini_api_key():
    """Retrieve Gemini API Key from .env if present."""
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.strip().startswith("#") and "GEMINI_API_KEY" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
    return os.environ.get("GEMINI_API_KEY")

def call_ai_for_fix(traceback_str, source_file_path, file_content):
    """
    Sends the traceback and buggy file content to Gemini (if API key available)
    or Ollama (local fallback) to generate a code fix.
    """
    prompt = f"""
    The Pinterest AI Agent crashed with the following Python traceback:
    
    CRASH TRACEBACK:
    {traceback_str}
    
    The error occurred in the file '{source_file_path}'.
    Here is the current content of '{source_file_path}':
    
    SOURCE CODE:
    ```python
    {file_content}
    ```
    
    Identify the bug causing the traceback. Correct the code to fix the bug.
    Make sure you preserve all existing functionality, comments, and structure.
    Return the ENTIRE corrected Python file code inside a single code block marked with ```python.
    Do not add extra explanations or conversational text.
    """

    api_key = get_gemini_api_key()
    if api_key:
        logger.info("Found GEMINI_API_KEY. Calling official Gemini API for self-healing code repair...")
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-flash-latest')
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}. Falling back to local Ollama...")
            
    # Local Ollama Fallback
    logger.info("Calling local Ollama server (qwen3) for code repair...")
    import urllib.request
    import json
    
    ollama_url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen3:latest",
        "prompt": prompt,
        "stream": False
    }
    try:
        req = urllib.request.Request(
            ollama_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=600) as response: # Increased timeout to 600s (10 minutes) for slow local Ollama runs
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get("response", "")
    except Exception as e:
        logger.error(f"Ollama local model call failed: {e}")
        
    return None

def extract_code_block(response_text):
    """Extracts python code block from markdown response."""
    if not response_text:
        return None
    match = re.search(r'```python\s*(.*?)\s*```', response_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1)
    # If no markdown block, return raw response if it looks like code
    if "import " in response_text or "def " in response_text:
        return response_text
    return None

def parse_traceback_file(traceback_str):
    """
    Parses traceback to find the last file belonging to the project that caused the crash.
    """
    # Find all file paths in project directory from traceback
    project_dir = os.getcwd().lower()
    matches = re.findall(r'File "([^"]+)", line (\d+)', traceback_str)
    
    for file_path, line_num in reversed(matches):
        full_path = os.path.abspath(file_path)
        if full_path.lower().startswith(project_dir) and "watchdog" not in file_path:
            return full_path
    return None

def monitor_and_run():
    logger.info("=== STARTING PINTEREST AGENT WATCHDOG RUNNER ===")
    
    while True:
        logger.info("Starting Pinterest main.py script...")
        # Run main.py as a subprocess, saving stdout/stderr output
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8"
        )
        
        # Monitor outputs and log them
        stderr_accumulator = []
        while process.poll() is None:
            # Read stdout dynamically (includes stderr)
            line = process.stdout.readline()
            if line:
                stderr_accumulator.append(line)
                sys.stdout.write(line)
                sys.stdout.flush()
                
        # Process completed. Check exit code
        exit_code = process.poll()
        logger.info(f"Process exited with code: {exit_code}")
        
        if exit_code == 0:
            logger.info("Pinterest Agent completed cycles successfully without crashes. Exiting Watchdog.")
            break
        else:
            logger.error("Pinterest Agent crashed! Starting Auto-Code-Repair (Self-Healing)...")
            
            # Read remainder of stdout since stderr is redirected
            remaining_stdout = process.stdout.read()
            stderr_accumulator.append(remaining_stdout)
            sys.stdout.write(remaining_stdout)
            sys.stdout.flush()
            
            traceback_str = "".join(stderr_accumulator)
            
            # Identify the project file that crashed
            crashed_file_path = parse_traceback_file(traceback_str)
            if not crashed_file_path or not os.path.exists(crashed_file_path):
                logger.error("Could not determine project file path from crash traceback. Restarting main.py in 60s...")
                time.sleep(60)
                continue
                
            logger.info(f"Targeting crashed file for repair: '{crashed_file_path}'")
            
            # Read crashed file content
            with open(crashed_file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                
            # Call AI backend to generate fix
            ai_response = call_ai_for_fix(traceback_str, crashed_file_path, file_content)
            corrected_code = extract_code_block(ai_response)
            
            if corrected_code and len(corrected_code.strip()) > 50:
                logger.info("AI generated a potential fix. Running validation checks...")
                
                # Create backup of current file
                backup_path = crashed_file_path + f".bak_{int(time.time())}"
                shutil.copy(crashed_file_path, backup_path)
                logger.info(f"Created source file backup: '{backup_path}'")
                
                # Write corrected code to file
                with open(crashed_file_path, "w", encoding="utf-8") as f:
                    f.write(corrected_code)
                    
                # Run syntax verification check using py_compile module
                try:
                    import py_compile
                    py_compile.compile(crashed_file_path, doraise=True)
                    logger.info("✅ Code syntax check passed! Auto-patched file successfully.")
                except Exception as compile_err:
                    logger.error(f"❌ AI generated invalid Python syntax: {compile_err}. Restoring backup...")
                    # Restore backup
                    shutil.copy(backup_path, crashed_file_path)
                    
            else:
                logger.error("AI response was invalid or empty. Could not generate code repair.")
                
            logger.info("Restarting Pinterest Agent main.py in 60 seconds...")
            time.sleep(60)

if __name__ == "__main__":
    try:
        monitor_and_run()
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user.")
