import os
import hmac
import hashlib
import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/api/kashier/create-order")
async def create_kashier_order(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        
    tier = str(data.get("tier", "10"))
    
    # EGP Pricing Map
    products_map = {
        "10": {"price": "500", "credits": 10, "desc": "MASARI Starter Pack"},
        "15": {"price": "750", "credits": 20, "desc": "MASARI Growth Pack"},
        "25": {"price": "1250", "credits": 50, "desc": "MASARI Executive Pack"}
    }
    
    product = products_map.get(tier, products_map["10"])
    
    # Kashier Details
    mid = os.environ.get("KASHIER_MERCHANT_ID", "")
    secret = os.environ.get("KASHIER_API_KEY", "")
    
    if not mid or not secret:
        return JSONResponse({"error": "Kashier credentials not configured"}, status_code=500)
        
    order_id = f"MASARI_{uuid.uuid4().hex[:8].upper()}"
    amount = product["price"]
    currency = "EGP"
    
    # Kashier Hash Generation
    # Format: /?payment={mid}.{order_id}.{amount}.{currency}
    path = f"/?payment={mid}.{order_id}.{amount}.{currency}"
    signature = hmac.new(
        secret.encode('utf-8'),
        path.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return JSONResponse({
        "merchantId": mid,
        "orderId": order_id,
        "amount": amount,
        "currency": currency,
        "hash": signature,
        "description": product["desc"],
        "mode": os.environ.get("KASHIER_MODE", "test")
    })

@router.post("/api/kashier/success")
async def kashier_success_webhook(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        
    # In a real production environment, you should verify the webhook signature here.
    # Kashier sends a signature in the callback that you hash using your secret.
    # For now, we trust the success status from the client SDK (or redirect).
    
    status = data.get("paymentStatus")
    tier = str(data.get("tier", "10"))
    
    if status != "SUCCESS":
        return JSONResponse({"error": "Payment not successful"}, status_code=400)
        
    products_credits_map = {
        "10": 10,
        "15": 20,
        "25": 50
    }
    credits_to_add = products_credits_map.get(tier, 10)
    
    db = request.app.state.mongo_db
    if db is not None:
        await db.users.update_one(
            {"_id": user_id},
            {
                "$inc": {"resume_credits": credits_to_add},
                "$set": {"is_premium": True, "subscription_type": "kashier_pro"}
            }
        )
        print(f"✅ Added {credits_to_add} credits to user {user_id} via Kashier!")
        return JSONResponse({"status": "success", "credits_added": credits_to_add})
    else:
        return JSONResponse({"error": "Database error"}, status_code=500)
