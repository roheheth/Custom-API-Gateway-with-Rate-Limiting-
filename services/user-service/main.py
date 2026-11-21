import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

# 1. Read MongoDB Connection URI from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/user_db")
client = AsyncIOMotorClient(MONGO_URI)
db = client.get_default_database() # Connects to 'user_db' database
users_collection = db["users"]     # Accesses 'users' collection

# 2. Database Seeding on Startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check if database has users
    count = await users_collection.count_documents({})
    if count == 0:
        # Seed initial data if database is empty
        await users_collection.insert_many([
            {"name": "Rohith"},
            {"name": "Alex"}
        ])
        print("Database seeded with initial users.")
    yield
    # Cleanup connection on shutdown
    client.close()

app = FastAPI(lifespan=lifespan)

# Pydantic schema for creating a user
class UserCreate(BaseModel):
    name: str

# 3. GET Endpoint: Retrieves users from database
@app.get("/")
async def get_users():
    cursor = users_collection.find({}, {"_id": 0, "name": 1})
    users_list = []
    async for document in cursor:
        users_list.append(document["name"])
        
    return {
        "service": "User Service",
        "users": users_list
    }

# 4. POST Endpoint: Creates a new user in database
@app.post("/")
async def create_user(user: UserCreate):
    # Check if user already exists
    existing_user = await users_collection.find_one({"name": user.name})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
        
    await users_collection.insert_one({"name": user.name})
    return {"message": "User created successfully", "name": user.name}