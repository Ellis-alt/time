import os
import requests
import time
import json
import re
from datetime import datetime
from pathlib import Path

# Configuration
TELEGRAM_TOKEN = os.getenv("TG_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
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
BUILD_START_TIME = os.getenv("BUILD_START_TIME", "")
ZIP_PATH = os.getenv("ZIP_PATH", "")
KPM_ENABLED = os.getenv("kpm", "false").lower() == "true"
CLANG_VERSION = os.getenv("clang", "unknown")

# Create unique message ID file for each matrix combination
LIVE_MESSAGE_ID_FILE = f"/tmp/live_message_{ROM_TYPE}_{KERNEL_BRANCH}.txt"

def telegram_api(method):
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"

def escape_markdown_text(text):
    """
    Escape only the characters that would break Markdown formatting in text content
    but keep the visual appearance clean
    """
    if not text:
        return text
    
    # Escape only the minimal set of characters that could break Markdown
    # but preserve visual appearance
    escape_chars = ['*', '`', '[', ']', '(', ')']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def escape_markdown_url(text):
    """
    Escape characters for URL content (more aggressive escaping)
    """
    if not text:
        return text
    
    # Escape characters that could break URLs in Markdown
    escape_chars = ['_', '*', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
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

def get_elapsed_time():
    if not BUILD_START_TIME:
        return "0 mins 0 secs"
    
    try:
        # Handle different time formats from GitHub Actions
        time_str = BUILD_START_TIME
        if 'Z' in time_str:
            time_str = time_str.replace('Z', '+00:00')
        
        # Parse ISO 8601 time
        start_time = datetime.fromisoformat(time_str)
        current_time = datetime.now().astimezone()
        
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
        print(f"Time string: {BUILD_START_TIME}")
        return "Unknown"

def build_live_message():
    # Build title with ROM type and kernel branch - no escaping in title
    title = f"🚀 Live Build Progress - {ROM_TYPE} ({KERNEL_BRANCH})"
    
    repo_url = f"{GITHUB_SERVER_URL}/{GITHUB_REPO}"
    branch_url = f"{KERNEL_SOURCE_URL}/tree/{KERNEL_BRANCH}"
    
    # Add KPM status
    kpm_status = "✅ Enabled" if KPM_ENABLED else "❌ Disabled"
    
    # For display text, use minimal escaping to keep it clean visually
    escaped_repo_name = escape_markdown_text(GITHUB_REPO)
    escaped_branch_name = KERNEL_BRANCH  # No escaping for display text - keep underscores visible
    escaped_clang = escape_markdown_text(CLANG_VERSION)
    escaped_stage = CURRENT_STAGE  # No escaping for stage - keep underscores visible
    
    # For URLs, we need to escape the branch name properly
    escaped_branch_url = escape_markdown_url(KERNEL_BRANCH)
    escaped_branch_url = branch_url.replace(KERNEL_BRANCH, escaped_branch_url)
    
    message = f"""*{title}*

*Workflow:* {GITHUB_WORKFLOW}
*Initiated By:* {GITHUB_ACTOR}
*Build ID:* `{GITHUB_RUN_ID}`
*Repository:* [{escaped_repo_name}]({repo_url})
*Branch:* [{escaped_branch_name}]({escaped_branch_url})
*Kernel Source:* [Link]({KERNEL_SOURCE_URL})
*Clang:* `{escaped_clang}`
*KPM:* {kpm_status}

*Progress:* {progress_bar(PROGRESS_PERCENT)}
*Stage:* `{escaped_stage}`
*Build Time:* {get_elapsed_time()}
"""
    return message

def build_final_message(status):
    title_icon = "✅" if status == "success" else "❌"
    status_text = "Success" if status == "success" else "Failed"
    
    title = f"{title_icon} Build {status_text} - {ROM_TYPE} ({KERNEL_BRANCH})"
    
    repo_url = f"{GITHUB_SERVER_URL}/{GITHUB_REPO}"
    branch_url = f"{KERNEL_SOURCE_URL}/tree/{KERNEL_BRANCH}"
    
    # Add KPM status
    kpm_status = "✅ Enabled" if KPM_ENABLED else "❌ Disabled"
    
    # For display text, use minimal escaping to keep it clean visually
    escaped_repo_name = escape_markdown_text(GITHUB_REPO)
    escaped_branch_name = KERNEL_BRANCH  # No escaping for display text
    escaped_clang = escape_markdown_text(CLANG_VERSION)
    
    # For URLs, we need to escape the branch name properly
    escaped_branch_url = escape_markdown_url(KERNEL_BRANCH)
    escaped_branch_url = branch_url.replace(KERNEL_BRANCH, escaped_branch_url)
    
    message = f"""*{title}*

*Workflow:* {GITHUB_WORKFLOW}
*Initiated By:* {GITHUB_ACTOR}
*Build ID:* `{GITHUB_RUN_ID}`
*Repository:* [{escaped_repo_name}]({repo_url})
*Branch:* [{escaped_branch_name}]({escaped_branch_url})
*Kernel Source:* [Link]({KERNEL_SOURCE_URL})
*Clang:* `{escaped_clang}`
*KPM:* {kpm_status}

*Build Time:* {get_elapsed_time()}
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
            
            # Try with a more conservative approach - remove problematic characters
            if "can't parse entities" in response.text:
                print("Retrying with safer formatting...")
                # Replace the message with a simpler version
                simple_text = text.replace('*', '').replace('`', '').replace('_', ' ')
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
