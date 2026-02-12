from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from app.services.spec_engine import SpecEngine
from app.utils.file_handler import save_upload_file
from app.database import get_supabase
from app.models.carrier import CarrierResponse

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
    db = get_supabase()
    response = db.table("carriers").select("*").execute()

    return {
        "success": True,
        "carriers": response.data
    }


@router.get("/{carrier_id}")
async def get_carrier(carrier_id: str):
    db = get_supabase()
    carrier_response = db.table("carriers").select("*").eq("id", carrier_id).maybeSingle().execute()

    if not carrier_response.data:
        raise HTTPException(status_code=404, detail="Carrier not found")

    spec_response = db.table("carrier_specs").select("*").eq("carrier_id", carrier_id).maybeSingle().execute()

    return {
        "success": True,
        "carrier": carrier_response.data,
        "specs": spec_response.data if spec_response.data else None
    }


@router.delete("/{carrier_id}")
async def delete_carrier(carrier_id: str):
    db = get_supabase()
    response = db.table("carriers").delete().eq("id", carrier_id).execute()

    return {
        "success": True,
        "message": "Carrier deleted successfully"
    }
