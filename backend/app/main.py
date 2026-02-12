from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import carriers, validation

app = FastAPI(
    title="Label & EDI Validation API",
    description="Specification-driven validation tool for shipping labels and EDI files",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(carriers.router)
app.include_router(validation.router)


@app.get("/")
async def root():
    return {
        "message": "Label & EDI Validation API",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
