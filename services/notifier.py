import subprocess
import logging

logger = logging.getLogger(__name__)

def notify(state, title, subtitle, body):
    if state == "CLEAR":
        return False
        
    sound = "Glass"
    if state in ["STRAND_RISK", "ACTIVE_RAIN", "WATERLOGGED"]:
        sound = "Basso"
        
    def escape(value):
        return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
    title, subtitle, body = escape(title), escape(subtitle), escape(body[:600])
    
    script = f'display notification "{body}" with title "Varuna: {title}" subtitle "{subtitle}" sound name "{sound}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True)
        return True
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False
