from typing import Dict, Any
from datetime import datetime
from app.database import get_database
from app.utils.pdf_extractor import (
    extract_structured_pdf_data,
    generate_rule_template_from_spec
)


class SpecEngine:
    def __init__(self):
        self.db = get_database()

    # ----------------------------------------
    # PROCESS SPEC UPLOAD (VERSIONED SAVE)
    # ----------------------------------------
    async def process_spec_upload(
        self,
        carrier_name: str,
        label_spec_path: str = None,
        edi_spec_path: str = None
    ) -> Dict[str, Any]:

        label_rules = {}
        edi_rules = {}

        # ---------------- LABEL SPEC ----------------
        if label_spec_path:
            spec_data = extract_structured_pdf_data(label_spec_path)

            label_rules, structured_conf = generate_rule_template_from_spec(
                spec_data,
                spec_type="label"
            )

            final_confidence = structured_conf

            if structured_conf < 0.6:
                try:
                    from app.services.ml_fallback.layout_engine import run_layout_fallback

                    ml_rules, ml_conf, _ = run_layout_fallback(
                        spec_data.get("image_bytes")
                    )

                    if isinstance(ml_rules, dict):
                        label_rules.update(ml_rules)

                    final_confidence = (
                        0.6 * structured_conf +
                        0.4 * ml_conf
                    )

                except Exception as e:
                    print(f"ML fallback failed: {e}")

            label_rules["confidence_score"] = round(final_confidence, 2)

        # ---------------- EDI SPEC ----------------
        if edi_spec_path:
            spec_data = extract_structured_pdf_data(edi_spec_path)

            edi_rules, edi_conf = generate_rule_template_from_spec(
                spec_data,
                spec_type="edi"
            )

            edi_rules["confidence_score"] = round(edi_conf, 2)

        # ---------------- VERSION HANDLING ----------------
        existing = await self.db.carriers.find_one({"carrier": carrier_name})

        if existing and "rules" in existing:
            new_version = len(existing["rules"]) + 1
        else:
            new_version = 1

        rule_entry = {
            "version": new_version,
            "created_at": datetime.utcnow(),
            "label_rules": label_rules,
            "edi_rules": edi_rules,
            "status": "active"
        }

        # ---------------- SAFE SAVE LOGIC ----------------
        if existing and "rules" in existing:

            # Mark previous versions inactive
            await self.db.carriers.update_one(
                {"carrier": carrier_name},
                {"$set": {"rules.$[].status": "inactive"}}
            )

            # Push new version
            await self.db.carriers.update_one(
                {"carrier": carrier_name},
                {"$push": {"rules": rule_entry}}
            )

        else:
            # Create new carrier OR initialize rules array
            await self.db.carriers.update_one(
                {"carrier": carrier_name},
                {
                    "$set": {"carrier": carrier_name},
                    "$push": {"rules": rule_entry}
                },
                upsert=True
            )

        return {
            "carrier_name": carrier_name,
            "version": new_version,
            "label_rules": label_rules,
            "edi_rules": edi_rules
        }

    # ----------------------------------------
    # GET ACTIVE RULE VERSION
    # ----------------------------------------
    async def get_carrier_rules(self, carrier_name: str) -> Dict[str, Any]:

        carrier = await self.db.carriers.find_one({"carrier": carrier_name})

        if not carrier or "rules" not in carrier:
            return {
                "label_rules": {},
                "edi_rules": {}
            }

        active_rule = next(
            (r for r in carrier["rules"] if r["status"] == "active"),
            None
        )

        if not active_rule:
            return {
                "label_rules": {},
                "edi_rules": {}
            }

        return {
            "version": active_rule.get("version"),
            "label_rules": active_rule.get("label_rules", {}),
            "edi_rules": active_rule.get("edi_rules", {})
        }

    # ----------------------------------------
    # ROLLBACK
    # ----------------------------------------
    async def rollback_to_version(
        self,
        carrier_name: str,
        version: int
    ) -> Dict[str, Any]:

        carrier = await self.db.carriers.find_one({"carrier": carrier_name})

        if not carrier or "rules" not in carrier:
            return {"success": False, "message": "Carrier or rules not found."}

        target = next(
            (r for r in carrier["rules"] if r["version"] == version),
            None
        )

        if not target:
            return {"success": False, "message": "Version not found."}

        # Mark all inactive
        await self.db.carriers.update_one(
            {"carrier": carrier_name},
            {"$set": {"rules.$[].status": "inactive"}}
        )

        # Activate selected
        await self.db.carriers.update_one(
            {
                "carrier": carrier_name,
                "rules.version": version
            },
            {
                "$set": {"rules.$.status": "active"}
            }
        )

        return {
            "success": True,
            "message": f"Rolled back to version {version}",
            "active_version": version
        }

    # ----------------------------------------
    # LIST VERSIONS
    # ----------------------------------------
    async def list_versions(self, carrier_name: str) -> Dict[str, Any]:

        carrier = await self.db.carriers.find_one({"carrier": carrier_name})

        if not carrier or "rules" not in carrier:
            return {"carrier": carrier_name, "versions": []}

        versions = []

        for rule in carrier["rules"]:
            versions.append({
                "version": rule.get("version"),
                "created_at": rule.get("created_at"),
                "status": rule.get("status"),
                "confidence_score": rule.get("label_rules", {}).get("confidence_score")
            })

        return {
            "carrier": carrier_name,
            "versions": versions
        }

    # ----------------------------------------
    # SIMULATE VALIDATION BETWEEN TWO VERSIONS
    # ----------------------------------------
    async def simulate_validation(
        self,
        carrier_name: str,
        version_1: int,
        version_2: int,
        label_path: str
    ) -> Dict[str, Any]:

        carrier = await self.db.carriers.find_one({"carrier": carrier_name})

        if not carrier or "rules" not in carrier:
            return {"error": "Carrier or rules not found."}

        rules = carrier["rules"]

        v1 = next((r for r in rules if r["version"] == version_1), None)
        v2 = next((r for r in rules if r["version"] == version_2), None)

        if not v1 or not v2:
            return {"error": "One or both versions not found."}

        from app.services.label_validator import LabelValidator
        from app.services.validation_diff import generate_validation_diff

        # Validate against version 1
        validator_v1 = LabelValidator(v1.get("label_rules", {}))
        result_v1 = await validator_v1.validate(label_path)

        # Validate against version 2
        validator_v2 = LabelValidator(v2.get("label_rules", {}))
        result_v2 = await validator_v2.validate(label_path)

        diff = generate_validation_diff(result_v1, result_v2)

        return {
            "carrier": carrier_name,
            "version_1": version_1,
            "version_2": version_2,
            "results": {
                "v1": result_v1,
                "v2": result_v2
            },
            "diff": diff
        }
