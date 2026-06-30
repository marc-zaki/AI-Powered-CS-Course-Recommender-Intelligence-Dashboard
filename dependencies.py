from fastapi import Request, Depends

async def get_db(request: Request):
    return request.app.state.mongo_db if hasattr(request.app.state, 'mongo_db') else None

async def get_current_user(request: Request, db=Depends(get_db)):
    user_id = request.session.get('user_id')
    if user_id and db is not None:
        return await db.users.find_one({"_id": user_id})
    return None
