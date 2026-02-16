from typing import Dict, Any
from app.database import get_database
from app.utils.pdf_extractor import (
    extract_text_from_pdf,
    generate_rule_template_from_spec
)


class SpecEngine:
    def __init__(self):
        self.db = get_database()

    async def process_spec_upload(
        self,
        carrier_name: str,
        label_spec_path: str = None,
        edi_spec_path: str = None
    ) -> Dict[str, Any]:

        # Generate rule templates
        label_rules = {}
        edi_rules = {}

        if label_spec_path:
            label_spec_text = extract_text_from_pdf(label_spec_path)
            label_rules = generate_rule_template_from_spec(label_spec_text, "label")

        if edi_spec_path:
            edi_spec_text = extract_text_from_pdf(edi_spec_path)
            edi_rules = generate_rule_template_from_spec(edi_spec_text, "edi")

        # Save or update carrier rules in MongoDB
        carrier_data = {
            "carrier": carrier_name,
            "label_rules": label_rules,
            "edi_rules": edi_rules,
            "label_spec_path": label_spec_path,
            "edi_spec_path": edi_spec_path
        }

        await self.db.carriers.update_one(
            {"carrier": carrier_name},
            {"$set": carrier_data},
            upsert=True
        )

        return {
            "carrier_name": carrier_name,
            "label_rules": label_rules,
            "edi_rules": edi_rules
        }

    async def get_carrier_rules(self, carrier_name: str) -> Dict[str, Any]:

        carrier = await self.db.carriers.find_one({"carrier": carrier_name})

        if not carrier:
            return {"label_rules": {}, "edi_rules": {}}

        return {
            "label_rules": carrier.get("label_rules", {}),
            "edi_rules": carrier.get("edi_rules", {})
        }
