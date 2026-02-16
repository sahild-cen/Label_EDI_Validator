from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb://localhost:27017"

client = AsyncIOMotorClient(MONGO_URI)
db = client["label_edi_validator"]

def get_database():
    return db
