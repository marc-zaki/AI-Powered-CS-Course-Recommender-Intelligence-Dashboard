from fastapi import Request
from jinja2 import pass_context

def flash(request: Request, message: str, category: str = "primary"):
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({"message": message, "category": category})

@pass_context
def get_flashed_messages(context, with_categories=False):
    request = context.get('request')
    if request is None:
        return []
    
    messages = request.session.pop('_messages', [])
    if with_categories:
        return [(msg['category'], msg['message']) for msg in messages]
    return [msg['message'] for msg in messages]
