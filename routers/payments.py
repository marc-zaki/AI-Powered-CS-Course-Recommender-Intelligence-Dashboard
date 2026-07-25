import os
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

def get_paypal_base_url():
    mode = os.environ.get("PAYPAL_MODE", "sandbox").lower()
    if mode == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"

async def get_paypal_access_token():
    client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
    if not client_id or not client_secret or client_id.startswith("paste_"):
        raise HTTPException(status_code=500, detail="PayPal API credentials not configured in .env")
        
    url = f"{get_paypal_base_url()}/v1/oauth2/token"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json", "Accept-Language": "en_US"}
        )
        if response.status_code != 200:
            print(f"⚠️ PayPal OAuth error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to authenticate with PayPal API")
        return response.json().get("access_token")

@router.post("/api/paypal/create-order")
async def create_paypal_order(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        
    tier = str(data.get("tier", "10"))
    
    products_map = {
        "10": {"price": "10.00", "credits": 10, "desc": "MASARI PRO 10 ATS Scans"},
        "15": {"price": "15.00", "credits": 20, "desc": "MASARI PRO 20 ATS Scans"},
        "25": {"price": "25.00", "credits": 50, "desc": "MASARI PRO 50 ATS Scans"}
    }
    
    product = products_map.get(tier, products_map["10"])
    
    access_token = await get_paypal_access_token()
    url = f"{get_paypal_base_url()}/v2/checkout/orders"
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": tier,
                "amount": {
                    "currency_code": "USD",
                    "value": product["price"]
                },
                "description": product["desc"]
            }
        ],
        "application_context": {
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        if response.status_code not in (200, 201):
            print(f"⚠️ PayPal create order error: {response.text}")
            return JSONResponse({"error": "Failed to create PayPal order"}, status_code=500)
            
        order_data = response.json()
        return JSONResponse({"id": order_data.get("id")})

@router.post("/api/paypal/capture-order")
async def capture_paypal_order(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        
    order_id = data.get("orderID")
    tier = str(data.get("tier", "10"))
    
    if not order_id:
        return JSONResponse({"error": "Missing orderID"}, status_code=400)
        
    products_map = {
        "10": 10,
        "15": 20,
        "25": 50
    }
    credits_to_add = products_map.get(tier, 10)
    
    access_token = await get_paypal_access_token()
    url = f"{get_paypal_base_url()}/v2/checkout/orders/{order_id}/capture"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={}
        )
        if response.status_code not in (200, 201):
            print(f"⚠️ PayPal capture error: {response.text}")
            return JSONResponse({"error": "Failed to capture PayPal order"}, status_code=500)
            
        capture_data = response.json()
        status = capture_data.get("status")
        
        if status == "COMPLETED":
            db = request.app.state.mongo_db
            if db is not None:
                await db.users.update_one(
                    {"_id": user_id},
                    {
                        "$inc": {"resume_credits": credits_to_add},
                        "$set": {"is_premium": True, "subscription_type": "paypal_pro"}
                    }
                )
                print(f"✅ Added {credits_to_add} credits to user {user_id} via PayPal!")
                return JSONResponse({"status": "success", "credits_added": credits_to_add})
            else:
                return JSONResponse({"error": "Database error"}, status_code=500)
        else:
            print(f"⚠️ PayPal order capture status: {status}")
            return JSONResponse({"error": f"Payment not completed (Status: {status})"}, status_code=400)
