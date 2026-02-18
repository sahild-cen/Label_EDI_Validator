import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.label_validator import LabelValidator
from app.services.edi_validator import EDIValidator
from app.utils.file_handler import save_upload_file, read_file_content, read_text_file
from app.database import get_database
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/api/validate", tags=["validation"])


# =========================
# LABEL VALIDATION
# =========================

@router.post("/label")
async def validate_label(
    carrier_id: str = Form(...),
    label_file: UploadFile = File(...)
):
    db = get_database()

    # -------------------------
    # Validate carrier
    # -------------------------
    try:
        carrier = await db.carriers.find_one({"_id": ObjectId(carrier_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid carrier ID")

    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")

    rules = carrier.get("rules", [])

    if not rules:
        raise HTTPException(
            status_code=400,
            detail="No rule versions found for this carrier. Upload specs first."
        )

    # Find active rule
    active_rule = next(
        (r for r in rules if r.get("status") == "active"),
        None
    )

    if not active_rule:
        raise HTTPException(
            status_code=400,
            detail="No active rule version found."
        )

    label_rules = active_rule.get("label_rules", {})

    if not label_rules:
        raise HTTPException(
            status_code=400,
            detail="No label rules found in active version."
        )


    # -------------------------
    # Save uploaded file
    # -------------------------
    label_path = await save_upload_file(label_file, "label")
    file_ext = os.path.splitext(label_path)[1].lower()

    print("DEBUG file_ext:", file_ext)

    validator = LabelValidator(label_rules)

    # -------------------------
    # FILE TYPE BRANCHING
    # -------------------------

    # ZPL / TXT text-based script
    if file_ext in [".zpl", ".txt"]:
        label_text = read_text_file(label_path)
        result = await validator.validate(
            label_text.encode("utf-8"),
            is_zpl=True
        )

    # Image files
    elif file_ext in [".png", ".jpg", ".jpeg"]:
        image_bytes = read_file_content(label_path)
        result = await validator.validate(
            image_bytes,
            is_zpl=False
        )

    # PDF (image-based)
    elif file_ext == ".pdf":
        # Read PDF directly as bytes (image-based PDF)
        image_bytes = read_file_content(label_path)

        result = await validator.validate(
            image_bytes,
            is_zpl=False
        )


    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported label file type"
        )

    # -------------------------
    # Save result to Mongo
    # -------------------------
    await db.validation_results.insert_one({
        "carrier_id": carrier_id,
        "validation_type": "label",
        "status": result["status"],
        "errors": result["errors"],
        "corrected_script": result.get("corrected_label_script"),
        "original_file_path": label_path,
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "validation": result
    }



@router.post("/edi")
async def validate_edi(
    carrier_id: str = Form(...),
    edi_file: UploadFile = File(...)
):
    db = get_database()

    try:
        carrier = await db.carriers.find_one({"_id": ObjectId(carrier_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid carrier ID")

    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")

    rules = carrier.get("rules", [])

    active_rule = next(
        (r for r in rules if r.get("status") == "active"),
        None
    )

    edi_rules = active_rule.get("edi_rules", {}) if active_rule else {}

    if not edi_rules:
        raise HTTPException(
            status_code=400,
            detail="No EDI rules found for this carrier. Upload specs first."
        )

    edi_path = await save_upload_file(edi_file, "edi")
    file_ext = os.path.splitext(edi_path)[1].lower()

    if file_ext not in [".edi", ".txt", ".csv", ".xml", ".json"]:
        raise HTTPException(status_code=400, detail="Unsupported EDI file format")

    try:
        edi_content = read_text_file(edi_path)
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read EDI file as text")

    validator = EDIValidator(edi_rules)
    result = await validator.validate(edi_content)

    await db.validation_results.insert_one({
        "carrier_id": carrier_id,
        "validation_type": "edi",
        "status": result["status"],
        "errors": result["errors"],
        "corrected_script": result.get("corrected_edi_script"),
        "original_file_path": edi_path,
        "created_at": datetime.utcnow()
    })

    return {
        "success": True,
        "validation": result
    }


# =========================
# VALIDATION HISTORY
# =========================

@router.get("/history/{carrier_id}")
async def get_validation_history(carrier_id: str, limit: int = 10):
    db = get_database()

    history = await db.validation_results.find(
        {"carrier_id": carrier_id}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)

    for item in history:
        item["_id"] = str(item["_id"])

    return {
        "success": True,
        "history": history
    }
