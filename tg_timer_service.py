import os
import requests
import time
import json
import threading
import sys
from datetime import datetime, timezone
from urllib.parse import quote

# Configuration
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_RUN_ID = os.getenv("GITHUB_RUN_ID")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "Build Kernel")
KERNEL_BRANCH = os.getenv("KERNEL_BRANCH", "unknown")
ROM_TYPE = os.getenv("ROM_TYPE", "unknown")
KPM_ENABLED = os.getenv("kpm", "false").lower() == "true"
CLANG_VERSION = os.getenv("clang", "unknown")
KERNEL_SOURCE_URL = os.getenv("KERNEL_SOURCE_URL", "")
GITHUB_ACTOR = os.getenv("GITHUB_ACTOR", "unknown")
GITHUB_SERVER_URL = "https://github.com"

# Global state
timer_thread = None
timer_running = False
current_stage = "Initializing"
progress_percent = "0"
message_id = None

def telegram_api(method):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"

def github_api(endpoint):
    return f"https://api.github.com/repos/{GITHUB_REPO}/{endpoint}"

def escape_markdown(text):
    if not text:
        return text
    escape_chars = ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def get_workflow_start_time():
    """Get workflow start time from GitHub API"""
    if not GITHUB_TOKEN or not GITHUB_RUN_ID:
        return None
    
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(github_api(f"actions/runs/{GITHUB_RUN_ID}"), headers=headers, timeout=10)
        
        if response.status_code == 200:
            run_data = response.json()
            created_at = run_data.get("created_at")
            if created_at:
                return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    except Exception as e:
        print(f"Error getting start time: {e}")
    return None

def get_elapsed_time(start_time):
    """Calculate elapsed time since start"""
    if not start_time:
        return "00:00:00"
    
    try:
        current_time = datetime.now(timezone.utc)
        elapsed = current_time - start_time
        total_seconds = int(elapsed.total_seconds())
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return "00:00:00"

def progress_bar(percent):
    filled = int(float(percent) / 5)
    empty = 20 - filled
    return f"[{'●' * filled}{'○' * empty}] {percent}%"

def build_message():
    start_time = get_workflow_start_time()
    elapsed = get_elapsed_time(start_time)
    
    title = f"🚀 Live Build - {ROM_TYPE} ({KERNEL_BRANCH})"
    
    return f"""*{title}*

*⏰ Elapsed Time:* `{elapsed}`
*📊 Progress:* {progress_bar(progress_percent)}
*🔧 Stage:* `{escape_markdown(current_stage)}`
*🌿 Branch:* `{escape_markdown(KERNEL_BRANCH)}`
*🛠️ Clang:* `{escape_markdown(CLANG_VERSION)}`
*🔐 KPM:* {'✅ Enabled' if KPM_ENABLED else '❌ Disabled'}
*👤 By:* `{GITHUB_ACTOR}`
*📦 Workflow:* `{GITHUB_WORKFLOW}`
*🆔 Run ID:* `{GITHUB_RUN_ID}`
"""

def send_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not available")
        return None
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(telegram_api("sendMessage"), json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()["result"]["message_id"]
    except Exception as e:
        print(f"Error sending message: {e}")
    return None

def edit_message(msg_id, text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": msg_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(telegram_api("editMessageText"), json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False

def delete_message(msg_id):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": msg_id,
    }
    try:
        requests.post(telegram_api("deleteMessage"), json=payload, timeout=10)
    except Exception:
        pass

def save_message_id(msg_id):
    try:
        with open("/tmp/telegram_msg_id.txt", "w") as f:
            f.write(str(msg_id))
    except Exception:
        pass

def load_message_id():
    try:
        with open("/tmp/telegram_msg_id.txt", "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None

def timer_worker():
    """Background worker that updates the message periodically"""
    global timer_running, message_id
    
    start_time = get_workflow_start_time()
    
    # Try to load existing message ID
    if message_id is None:
        message_id = load_message_id()
    
    # Send initial message if needed
    if message_id is None:
        message = build_message()
        message_id = send_message(message)
        if message_id:
            save_message_id(message_id)
        else:
            print("Failed to send initial message")
            return
    
    timer_running = True
    update_count = 0
    
    while timer_running:
        try:
            message = build_message()
            success = edit_message(message_id, message)
            
            if not success:
                # Message might have been deleted, try to recreate
                message_id = send_message(message)
                if message_id:
                    save_message_id(message_id)
                else:
                    print("Failed to recreate message")
                    break
            
            update_count += 1
            time.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            print(f"Error in timer worker: {e}")
            time.sleep(10)

def start_timer():
    """Start the timer service"""
    global timer_thread
    
    if timer_thread and timer_thread.is_alive():
        return
    
    timer_thread = threading.Thread(target=timer_worker, daemon=True)
    timer_thread.start()
    print("Timer service started")

def stop_timer():
    """Stop the timer service"""
    global timer_running
    timer_running = False
    print("Timer service stopped")

def update_stage(stage, progress):
    """Update the current stage and progress"""
    global current_stage, progress_percent
    current_stage = stage
    progress_percent = str(progress)
    print(f"Stage updated: {stage} - {progress}%")

def send_final_message(status, zip_path=None):
    """Send final message when build completes"""
    stop_timer()
    
    # Delete the live message
    msg_id = load_message_id()
    if msg_id:
        delete_message(msg_id)
    
    # Send final summary
    title_icon = "✅" if status == "success" else "❌"
    status_text = "Completed Successfully" if status == "success" else "Failed"
    
    start_time = get_workflow_start_time()
    elapsed = get_elapsed_time(start_time) if start_time else "Unknown"
    
    final_message = f"""*{title_icon} Build {status_text} - {ROM_TYPE} ({KERNEL_BRANCH})*

*⏱️ Total Time:* `{elapsed}`
*🌿 Branch:* `{escape_markdown(KERNEL_BRANCH)}`
*🛠️ Clang:* `{escape_markdown(CLANG_VERSION)}`
*🔐 KPM:* {'✅ Enabled' if KPM_ENABLED else '❌ Disabled'}
*👤 By:* `{GITHUB_ACTOR}`
*📦 Workflow:* `{GITHUB_WORKFLOW}`

*Status:* {status_text}
"""
    
    send_message(final_message)
    print("Final message sent")

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            start_timer()
            
        elif command == "update":
            if len(sys.argv) > 3:
                stage = sys.argv[2]
                progress = sys.argv[3]
                update_stage(stage, progress)
                
        elif command == "end":
            status = sys.argv[2] if len(sys.argv) > 2 else "unknown"
            send_final_message(status)
            
    else:
        # Interactive mode for testing
        start_timer()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_timer()

if __name__ == "__main__":
    main()
