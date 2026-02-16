from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from app.services.spec_engine import SpecEngine
from app.utils.file_handler import save_upload_file
from app.database import get_database
from bson import ObjectId

router = APIRouter(prefix="/api/carriers", tags=["carriers"])


@router.post("/upload")
async def upload_carrier_spec(
    carrier_name: str = Form(...),
    label_spec: Optional[UploadFile] = File(None),
    edi_spec: Optional[UploadFile] = File(None)
):
    spec_engine = SpecEngine()

    label_spec_path = None
    edi_spec_path = None

    if label_spec:
        label_spec_path = await save_upload_file(label_spec, "label_spec")

    if edi_spec:
        edi_spec_path = await save_upload_file(edi_spec, "edi_spec")

    result = await spec_engine.process_spec_upload(
        carrier_name=carrier_name,
        label_spec_path=label_spec_path,
        edi_spec_path=edi_spec_path
    )

    return {
        "success": True,
        "message": f"Carrier '{carrier_name}' specs uploaded successfully",
        "data": result
    }


@router.get("/list")
async def list_carriers():
    db = get_database()
    carriers = await db.carriers.find({}, {"_id": 1, "carrier": 1}).to_list(length=None)

    # Convert ObjectId to string
    for carrier in carriers:
        carrier["_id"] = str(carrier["_id"])

    return {
        "success": True,
        "carriers": carriers
    }


@router.get("/{carrier_id}")
async def get_carrier(carrier_id: str):
    db = get_database()

    try:
        carrier = await db.carriers.find_one({"_id": ObjectId(carrier_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid carrier ID")

    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")

    carrier["_id"] = str(carrier["_id"])

    return {
        "success": True,
        "carrier": carrier
    }


@router.delete("/{carrier_id}")
async def delete_carrier(carrier_id: str):
    db = get_database()

    try:
        result = await db.carriers.delete_one({"_id": ObjectId(carrier_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid carrier ID")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Carrier not found")

    return {
        "success": True,
        "message": "Carrier deleted successfully"
    }
