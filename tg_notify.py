import os
import requests
import time
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# Configuration
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "unknown/repo")
GITHUB_ACTOR = os.getenv("GITHUB_ACTOR", "unknown")
GITHUB_SERVER_URL = "https://github.com"
GITHUB_RUN_ID = os.getenv("GITHUB_RUN_ID", "unknown")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "Build Kernel")
KERNEL_BRANCH = os.getenv("KERNEL_BRANCH", "unknown")
KERNEL_SOURCE_URL = os.getenv("KERNEL_SOURCE_URL", "")
ROM_TYPE = os.getenv("ROM_TYPE", "unknown")
BUILD_STATUS = os.getenv("BUILD_STATUS", "in_progress")
CURRENT_STAGE = os.getenv("CURRENT_STAGE", "Initializing")
PROGRESS_PERCENT = os.getenv("PROGRESS_PERCENT", "0")
ZIP_PATH = os.getenv("ZIP_PATH", "")
KPM_ENABLED = os.getenv("kpm", "false").lower() == "true"
CLANG_VERSION = os.getenv("clang", "unknown")

# Create unique message ID file for each matrix combination
LIVE_MESSAGE_ID_FILE = f"/tmp/live_message_{ROM_TYPE}_{KERNEL_BRANCH}.txt"

def telegram_api(method):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"

def github_api(endpoint):
    return f"https://api.github.com/repos/{GITHUB_REPO}/{endpoint}"

def escape_markdown_text(text):
    """
    Escape only the characters that would break Markdown formatting in text content
    but keep the visual appearance clean
    """
    if not text:
        return text
    
    escape_chars = ['*', '`', '[', ']', '(', ')']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}P{suffix}"

def progress_bar(percent):
    filled = int(float(percent) / 5)
    empty = 20 - filled
    return f"[{'●' * filled}{'○' * empty}] ({percent}%)"

def get_workflow_start_time():
    """Get the actual workflow start time from GitHub API"""
    if not GITHUB_TOKEN or not GITHUB_RUN_ID:
        print("GitHub token or run ID not available")
        return None
    
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get workflow run details
        response = requests.get(github_api(f"actions/runs/{GITHUB_RUN_ID}"), headers=headers, timeout=10)
        if response.status_code == 200:
            run_data = response.json()
            created_at = run_data.get("created_at")
            if created_at:
                # Parse GitHub's ISO 8601 format
                return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        print(f"Failed to get workflow start time: {response.status_code}")
        return None
        
    except Exception as e:
        print(f"Error getting workflow start time: {e}")
        return None

def get_elapsed_time():
    """Calculate elapsed time since workflow started using GitHub API"""
    start_time = get_workflow_start_time()
    if not start_time:
        return "0 mins 0 secs"
    
    try:
        current_time = datetime.now(timezone.utc)
        elapsed = current_time - start_time
        total_seconds = int(elapsed.total_seconds())
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours} hrs {minutes} mins {seconds} secs"
        elif minutes > 0:
            return f"{minutes} mins {seconds} secs"
        else:
            return f"{seconds} secs"
            
    except Exception as e:
        print(f"Error calculating elapsed time: {e}")
        return "Unknown"

def get_live_elapsed_time():
    """Get elapsed time with live updating capability"""
    start_time = get_workflow_start_time()
    if not start_time:
        return "⏱️ 0s"
    
    try:
        current_time = datetime.now(timezone.utc)
        elapsed = current_time - start_time
        total_seconds = int(elapsed.total_seconds())
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # Create a live timer format
        if hours > 0:
            return f"⏱️ {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"⏱️ {minutes:02d}:{seconds:02d}"
            
    except Exception as e:
        print(f"Error calculating live elapsed time: {e}")
        return "⏱️ --:--"

def build_live_message():
    title = f"🚀 Live Build Progress - {ROM_TYPE} ({KERNEL_BRANCH})"
    
    repo_url = f"{GITHUB_SERVER_URL}/{GITHUB_REPO}"
    branch_url = f"{KERNEL_SOURCE_URL.removesuffix('.git')}/tree/{KERNEL_BRANCH}"
    
    kpm_status = "Enabled" if KPM_ENABLED else "Disabled"
    
    escaped_repo_name = escape_markdown_text(GITHUB_REPO)
    escaped_branch_name = KERNEL_BRANCH
    escaped_clang = escape_markdown_text(CLANG_VERSION)
    escaped_stage = CURRENT_STAGE
    
    # Get live elapsed time
    elapsed_time = get_live_elapsed_time()
    
    message = f"""*{title}*

*Workflow:* {GITHUB_WORKFLOW}
*Initiated By:* {GITHUB_ACTOR}
*Build ID:* `{GITHUB_RUN_ID}`
*Repository:* [{escaped_repo_name}]({repo_url})
*Branch:* [{escaped_branch_name}]({branch_url})
*Kernel Source:* [Link]({KERNEL_SOURCE_URL})
*Clang:* `{escaped_clang}`
*KPM:* {kpm_status}

*Progress:* {progress_bar(PROGRESS_PERCENT)}
*Stage:* `{escaped_stage}`
*Elapsed Time:* {elapsed_time}
"""
    return message

def build_final_message(status):
    title_icon = "✅" if status == "success" else "❌"
    status_text = "Success" if status == "success" else "Failed"
    
    title = f"{title_icon} Build {status_text} - {ROM_TYPE} ({KERNEL_BRANCH})"
    
    repo_url = f"{GITHUB_SERVER_URL}/{GITHUB_REPO}"
    branch_url = f"{KERNEL_SOURCE_URL.removesuffix('.git')}/tree/{KERNEL_BRANCH}"
    
    kpm_status = "Enabled" if KPM_ENABLED else "Disabled"
    
    escaped_repo_name = escape_markdown_text(GITHUB_REPO)
    escaped_branch_name = KERNEL_BRANCH
    escaped_clang = escape_markdown_text(CLANG_VERSION)
    
    # Get final elapsed time
    elapsed_time = get_elapsed_time()
    
    message = f"""*{title}*

*Workflow:* {GITHUB_WORKFLOW}
*Initiated By:* {GITHUB_ACTOR}
*Build ID:* `{GITHUB_RUN_ID}`
*Repository:* [{escaped_repo_name}]({repo_url})
*Branch:* [{escaped_branch_name}]({branch_url})
*Kernel Source:* [Link]({KERNEL_SOURCE_URL})
*Clang:* `{escaped_clang}`
*KPM:* {kpm_status}

*Total Build Time:* {elapsed_time}
"""
    return message

def send_message(text, parse_mode="Markdown"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, skipping message")
        return None
        
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(telegram_api("sendMessage"), json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("result", {}).get("message_id")
        else:
            print(f"Failed to send message: {response.status_code} - {response.text}")
            
            if "can't parse entities" in response.text:
                print("Retrying with safer formatting...")
                lines = text.split('\n')
                simple_lines = []
                for line in lines:
                    if line.strip().startswith('*') and line.strip().endswith('*'):
                        clean_line = line.replace('*', '').strip()
                        simple_lines.append(clean_line)
                    elif '[' in line and '](' in line and ')' in line:
                        match = re.search(r'\[([^\]]+)\]\([^)]+\)', line)
                        if match:
                            simple_lines.append(match.group(1))
                        else:
                            simple_lines.append(line)
                    else:
                        simple_lines.append(line)
                
                simple_text = '\n'.join(simple_lines)
                payload["text"] = simple_text
                payload.pop("parse_mode", None)
                response = requests.post(telegram_api("sendMessage"), json=payload, timeout=10)
                if response.status_code == 200:
                    return response.json().get("result", {}).get("message_id")
            
            return None
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def edit_message(message_id, text, parse_mode="Markdown"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, skipping edit")
        return False
        
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(telegram_api("editMessageText"), json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"Failed to edit message: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error editing message: {e}")
        return False

def delete_message(message_id):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, skipping delete")
        return
        
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
    }
    try:
        requests.post(telegram_api("deleteMessage"), json=payload, timeout=10)
    except Exception as e:
        print(f"Error deleting message: {e}")

def save_message_id(message_id):
    try:
        with open(LIVE_MESSAGE_ID_FILE, 'w') as f:
            f.write(str(message_id))
    except Exception as e:
        print(f"Error saving message ID: {e}")

def load_message_id():
    try:
        with open(LIVE_MESSAGE_ID_FILE, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError, Exception):
        return None

def upload_file_with_progress(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False

    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)

    upload_msg = f"""📦 *Uploading File*
*Name:* `{filename}`
*Size:* {sizeof_fmt(file_size)}
*Status:* Uploading...
"""
    message_id = send_message(upload_msg)
    if not message_id:
        return False

    # Simulate progress
    for progress in range(0, 101, 10):
        progress_text = f"*Progress:* {progress_bar(str(progress))}"
        updated_msg = upload_msg + "\n" + progress_text
        edit_message(message_id, updated_msg)
        time.sleep(0.3)

    # Actually upload the file
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                telegram_api("sendDocument"),
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": f"📦 {filename}"},
                files={"document": (filename, f)},
                timeout=60
            )
        
        if response.status_code == 200:
            # Update status and then delete
            uploaded_msg = upload_msg.replace("Uploading...", "✅ Uploaded")
            edit_message(message_id, uploaded_msg)
            time.sleep(2)
            delete_message(message_id)
            return True
        else:
            error_msg = upload_msg.replace("Uploading...", "❌ Upload Failed")
            edit_message(message_id, error_msg)
            return False
    except Exception as e:
        print(f"Error uploading file: {e}")
        error_msg = upload_msg.replace("Uploading...", "❌ Upload Error")
        edit_message(message_id, error_msg)
        return False

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not set, skipping notification")
        return

    action = os.getenv("TELEGRAM_ACTION", "start")
    
    print(f"Telegram action: {action}")
    print(f"ROM_TYPE: {ROM_TYPE}")
    print(f"KERNEL_BRANCH: {KERNEL_BRANCH}")
    print(f"BUILD_STATUS: {BUILD_STATUS}")
    print(f"CURRENT_STAGE: {CURRENT_STAGE}")
    print(f"PROGRESS_PERCENT: {PROGRESS_PERCENT}")
    print(f"Message ID file: {LIVE_MESSAGE_ID_FILE}")
    
    if action == "start":
        # Send initial live message
        message = build_live_message()
        message_id = send_message(message)
        if message_id:
            save_message_id(message_id)
            print(f"Live message sent with ID: {message_id}")
    
    elif action == "update":
        # Update existing live message
        message_id = load_message_id()
        if message_id:
            message = build_live_message()
            success = edit_message(message_id, message)
            if not success:
                print("Failed to update message, sending new one")
                message_id = send_message(message)
                if message_id:
                    save_message_id(message_id)
        else:
            message = build_live_message()
            message_id = send_message(message)
            if message_id:
                save_message_id(message_id)
    
    elif action == "end":
        message_id = load_message_id()
        if message_id:
            delete_message(message_id)
        
        # Send final status message
        status = "success" if BUILD_STATUS == "success" else "failure"
        message = build_final_message(status)
        send_message(message)
        
        # Upload file if build was successful
        if BUILD_STATUS == "success" and ZIP_PATH and os.path.exists(ZIP_PATH):
            print(f"Uploading file: {ZIP_PATH}")
            upload_file_with_progress(ZIP_PATH)
        else:
            print(f"Not uploading file - Status: {BUILD_STATUS}, ZIP exists: {os.path.exists(ZIP_PATH) if ZIP_PATH else 'No ZIP_PATH'}")

if __name__ == "__main__":
    main()
