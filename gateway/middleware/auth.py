import os
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from logger import logger

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set") #earlier it was os.getenv("JWT_SECRET", "mysuperkey"), now creates a runtimeError if there is no secretkey in env file

async def auth_middleware(request: Request):
    auth_header = request.headers.get("authorization")

    # No token
    if not auth_header:
        logger.error(
            f"Unauthorized Access Attempt: {request.url.path}"
        )
        return JSONResponse(
            status_code=401,
            content={
                "message": "No token provided"
            }
        )

    try:
        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise ValueError("Invalid authorization header format")
            
        token = parts[1]
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        request.state.user = decoded
        return None  # Success, continue validation
    except Exception as error:
        logger.error(
            f"JWT Validation Failed: {str(error)}"
        )
        return JSONResponse(
            status_code=403,
            content={
                "message": "Invalid token"
            }
        )
