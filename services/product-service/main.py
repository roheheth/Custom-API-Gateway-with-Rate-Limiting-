import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

# 1. Read MongoDB Connection URI from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/product_db")
client = AsyncIOMotorClient(MONGO_URI)
db = client.get_default_database() # Connects to 'product_db' database
products_collection = db["products"] # Accesses 'products' collection

# 2. Database Seeding on Startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check if database has products
    count = await products_collection.count_documents({})
    if count == 0:
        # Seed initial data if database is empty
        await products_collection.insert_many([
            {"name": "Laptop"},
            {"name": "Phone"}
        ])
        print("Database seeded with initial products.")
    yield
    # Cleanup connection on shutdown
    client.close()

app = FastAPI(lifespan=lifespan)

# Pydantic schema for creating a product
class ProductCreate(BaseModel):
    name: str

# 3. GET Endpoint: Retrieves products from database
@app.get("/")
async def get_products():
    cursor = products_collection.find({}, {"_id": 0, "name": 1})
    products_list = []
    async for document in cursor:
        products_list.append(document["name"])
        
    return {
        "service": "Product Service",
        "products": products_list
    }

# 4. POST Endpoint: Creates a new product in database
@app.post("/")
async def create_product(product: ProductCreate):
    # Check if product already exists
    existing_product = await products_collection.find_one({"name": product.name})
    if existing_product:
        raise HTTPException(status_code=400, detail="Product already exists")
        
    await products_collection.insert_one({"name": product.name})
    return {"message": "Product created successfully", "name": product.name}