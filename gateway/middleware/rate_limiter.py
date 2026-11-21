import time
from fastapi import Request
from fastapi.responses import JSONResponse
from config.redis_config import redis_client
from logger import logger

# 1. Define the Token Bucket Lua Script
# This runs inside Redis. It calculates the elapsed time since the last request,
# adds refilled tokens, and decrements 1 token if available.
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Get the current state of the bucket
local data = redis.call('HMGET', key, 'tokens', 'last_updated')
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if not tokens then
    -- First request: Initialize the bucket to maximum capacity
    tokens = capacity
    last_updated = now
else
    -- Calculate elapsed time and add refilled tokens to the bucket
    local elapsed = now - last_updated
    if elapsed > 0 then
        tokens = math.min(capacity, tokens + (elapsed * refill_rate))
        last_updated = now
    end
end

-- If we have at least 1 token, consume it and allow the request
if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, 60)
    return {1, math.floor(tokens)} -- Return [Allowed (1), Remaining Tokens]
else
    -- Not enough tokens: Block the request
    redis.call('HMSET', key, 'tokens', tokens, 'last_updated', last_updated)
    redis.call('EXPIRE', key, 60)
    return {0, 0} -- Return [Blocked (0), Remaining Tokens (0)]
end
"""

# Compile/Register the script in Redis
rate_limit_script = redis_client.register_script(LUA_TOKEN_BUCKET)

async def rate_limiter(request: Request):
    try:
        # IP Address of the client
        ip = request.client.host if request.client else "127.0.0.1"

        # User Tier (free or premium)
        user_tier = "free"
        if hasattr(request.state, "user") and request.state.user:
            user_tier = request.state.user.get("role", "free")

        # Limits configuration
        limits = {
            "free": {"capacity": 5, "refill_time_sec": 60},      # 5 requests per 60s
            "premium": {"capacity": 20, "refill_time_sec": 60}   # 20 requests per 60s
        }
        
        config = limits.get(user_tier, limits["free"])
        capacity = config["capacity"]
        # Refill rate = tokens added per second (e.g. 5 tokens / 60 seconds = 0.083 tokens/sec)
        refill_rate = capacity / config["refill_time_sec"]

        # Redis key for this IP
        key = f"rate_limit:{ip}"
        
        # Current time in seconds (float)
        now = time.time()

        # 2. Run the Lua script atomically in Redis
        # Keys must be passed as a list; ARGV values must be passed after
        result = await rate_limit_script(keys=[key], args=[capacity, refill_rate, now])
        
        allowed, remaining_tokens = result[0], result[1]

        # 3. Block request if allowed flag is 0
        if allowed == 0:
            logger.error(
                f"Rate Limit Exceeded (Token Bucket) | IP: {ip} | Tier: {user_tier}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "message": "Too many requests",
                    "limit": capacity
                }
            )

        # Optional: You can inject remaining tokens into response headers if you want!
        return None

    except Exception as error:
        logger.error(f"Rate Limiter Error: {str(error)}")
        return JSONResponse(
            status_code=500,
            content={
                "message": "Rate limiter error"
            }
        )