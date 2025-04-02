from telegram import Update
from datetime import datetime

def get_current_time()-> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_update(update: Update):
    user = update.effective_user
    msg = update.effective_message 
    log_message:str = ""
    if user:
        log_message += f"User {user.first_name} @{user.username} ({user.id}) used bot. "
    else:
        log("Uknown User used bot.")
    if msg and msg.text:
        log_message += f"Command: {msg.text}"
    log(log_message,"<Update>")

def log(message_log:str, subject = None):
    print(f"[{get_current_time()}] {f'[{subject}]' if subject else ''} {message_log}")