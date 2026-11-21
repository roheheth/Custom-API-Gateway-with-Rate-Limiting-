import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

# 1. Read MongoDB Connection URI from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/order_db")
client = AsyncIOMotorClient(MONGO_URI)
db = client.get_default_database() # Connects to 'order_db' database
orders_collection = db["orders"]   # Accesses 'orders' collection

# 2. Database Seeding on Startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check if database has orders
    count = await orders_collection.count_documents({})
    if count == 0:
        # Seed initial data if database is empty
        await orders_collection.insert_many([
            {"order_id": 101},
            {"order_id": 102}
        ])
        print("Database seeded with initial orders.")
    yield
    # Cleanup connection on shutdown
    client.close()

app = FastAPI(lifespan=lifespan)

# Pydantic schema for creating an order
class OrderCreate(BaseModel):
    order_id: int

# 3. GET Endpoint: Retrieves orders from database
@app.get("/")
async def get_orders():
    cursor = orders_collection.find({}, {"_id": 0, "order_id": 1})
    orders_list = []
    async for document in cursor:
        orders_list.append(document["order_id"])
        
    return {
        "service": "Order Service",
        "orders": orders_list
    }

# 4. POST Endpoint: Creates a new order in database
@app.post("/")
async def create_order(order: OrderCreate):
    # Check if order already exists
    existing_order = await orders_collection.find_one({"order_id": order.order_id})
    if existing_order:
        raise HTTPException(status_code=400, detail="Order already exists")
        
    await orders_collection.insert_one({"order_id": order.order_id})
    return {"message": "Order created successfully", "order_id": order.order_id}