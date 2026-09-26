import subprocess
import logging

logger = logging.getLogger(__name__)

def notify(state, title, subtitle, body):
    if state == "CLEAR":
        return
        
    sound = "Glass"
    if state in ["STRAND_RISK", "ACTIVE_RAIN", "WATERLOGGED"]:
        sound = "Basso"
        
    title = title.replace('"', '\\"')
    subtitle = subtitle.replace('"', '\\"')
    body = body.replace('"', '\\"')
    
    script = f'display notification "{body}" with title "Varuna: {title}" subtitle "{subtitle}" sound name "{sound}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True)
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
