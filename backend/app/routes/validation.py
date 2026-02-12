from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.spec_engine import SpecEngine
from app.services.label_validator import LabelValidator
from app.services.edi_validator import EDIValidator
from app.utils.file_handler import save_upload_file, read_file_content, read_text_file
from app.database import get_supabase

router = APIRouter(prefix="/api/validate", tags=["validation"])


@router.post("/label")
async def validate_label(
    carrier_id: str = Form(...),
    label_file: UploadFile = File(...),
    is_zpl: bool = Form(False)
):
    spec_engine = SpecEngine()
    rules = await spec_engine.get_carrier_rules(carrier_id)
    label_rules = rules.get("label_rules", {})

    if not label_rules:
        raise HTTPException(
            status_code=400,
            detail="No label rules found for this carrier. Please upload carrier specs first."
        )

    label_path = await save_upload_file(label_file, "label")

    if is_zpl:
        label_data = read_text_file(label_path).encode("utf-8")
    else:
        label_data = read_file_content(label_path)

    validator = LabelValidator(label_rules)
    result = await validator.validate(label_data, is_zpl=is_zpl)

    db = get_supabase()
    db.table("validation_results").insert({
        "carrier_id": carrier_id,
        "validation_type": "label",
        "status": result["status"],
        "errors": result["errors"],
        "corrected_script": result.get("corrected_label_script"),
        "original_file_url": label_path
    }).execute()

    return {
        "success": True,
        "validation": result
    }


@router.post("/edi")
async def validate_edi(
    carrier_id: str = Form(...),
    edi_file: UploadFile = File(...)
):
    spec_engine = SpecEngine()
    rules = await spec_engine.get_carrier_rules(carrier_id)
    edi_rules = rules.get("edi_rules", {})

    if not edi_rules:
        raise HTTPException(
            status_code=400,
            detail="No EDI rules found for this carrier. Please upload carrier specs first."
        )

    edi_path = await save_upload_file(edi_file, "edi")
    edi_content = read_text_file(edi_path)

    validator = EDIValidator(edi_rules)
    result = await validator.validate(edi_content)

    db = get_supabase()
    db.table("validation_results").insert({
        "carrier_id": carrier_id,
        "validation_type": "edi",
        "status": result["status"],
        "errors": result["errors"],
        "corrected_script": result.get("corrected_edi_script"),
        "original_file_url": edi_path
    }).execute()

    return {
        "success": True,
        "validation": result
    }


@router.get("/history/{carrier_id}")
async def get_validation_history(carrier_id: str, limit: int = 10):
    db = get_supabase()
    response = db.table("validation_results") \
        .select("*") \
        .eq("carrier_id", carrier_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return {
        "success": True,
        "history": response.data
    }
