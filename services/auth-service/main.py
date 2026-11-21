import os
import datetime
import bcrypt
import jwt
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

# 1. Database connection config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/auth_db")
JWT_SECRET = os.getenv("JWT_SECRET", "mySuperSecretKey")

client = AsyncIOMotorClient(MONGO_URI)
db = client.get_default_database()
users_collection = db["users"]

app = FastAPI()

# 2. Pydantic request models
class UserRegister(BaseModel):
    username: str
    password: str
    role: str = "free" # Can be "free" or "premium"

class UserLogin(BaseModel):
    username: str
    password: str

# 3. Password Helper Functions (using bcrypt)
def hash_password(password: str) -> str:
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify the plain text password matches the hash
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# 4. Registration Endpoint
@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserRegister):
    # Check if username is already taken
    existing_user = await users_collection.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Hash password and insert user into MongoDB
    hashed_pwd = hash_password(user.password)
    new_user = {
        "username": user.username,
        "password": hashed_pwd,
        "role": user.role
    }
    await users_collection.insert_one(new_user)
    return {"message": "User registered successfully", "username": user.username}

# 5. Login Endpoint
@app.post("/login")
async def login(user: UserLogin):
    # Retrieve user from database
    db_user = await users_collection.find_one({"username": user.username})
    
    # Verify username and password
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Generate JWT token (expires in 1 hour)
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    payload = {
        "id": str(db_user["_id"]),
        "username": db_user["username"],
        "role": db_user["role"],
        "exp": expiration
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    return {"token": token}