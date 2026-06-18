from fastapi.templating import Jinja2Templates
from flash import get_flashed_messages

templates = Jinja2Templates(directory="templates")

def check_is_super_admin(user):
    return user and user.get("email", "") in ["mzaki2222@gmail.com", "yossif7zaki@gmail.com"]

def is_premium(user):
    if not user:
        return False
    is_super = check_is_super_admin(user)
    return user.get('is_premium', False) or user.get('role') in ['admin', 'super_admin'] or is_super

templates.env.globals["get_flashed_messages"] = get_flashed_messages
templates.env.globals["is_premium"] = is_premium
templates.env.globals["check_is_super_admin"] = check_is_super_admin
