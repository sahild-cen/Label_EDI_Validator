from typing import Dict, Any
from app.database import get_supabase
from app.utils.pdf_extractor import extract_text_from_pdf, generate_rule_template_from_spec


class SpecEngine:
    def __init__(self):
        self.db = get_supabase()

    async def process_spec_upload(
        self,
        carrier_name: str,
        label_spec_path: str = None,
        edi_spec_path: str = None
    ) -> Dict[str, Any]:
        carrier_response = self.db.table("carriers").select("*").eq("name", carrier_name).maybeSingle().execute()

        if carrier_response.data:
            carrier_id = carrier_response.data["id"]
        else:
            new_carrier = self.db.table("carriers").insert({"name": carrier_name}).execute()
            carrier_id = new_carrier.data[0]["id"]

        label_rules = {}
        edi_rules = {}

        if label_spec_path:
            label_spec_text = extract_text_from_pdf(label_spec_path)
            label_rules = generate_rule_template_from_spec(label_spec_text, "label")

        if edi_spec_path:
            edi_spec_text = extract_text_from_pdf(edi_spec_path)
            edi_rules = generate_rule_template_from_spec(edi_spec_text, "edi")

        existing_spec = self.db.table("carrier_specs").select("*").eq("carrier_id", carrier_id).maybeSingle().execute()

        spec_data = {
            "carrier_id": carrier_id,
            "label_rules": label_rules,
            "edi_rules": edi_rules,
            "label_spec_url": label_spec_path,
            "edi_spec_url": edi_spec_path
        }

        if existing_spec.data:
            result = self.db.table("carrier_specs").update(spec_data).eq("carrier_id", carrier_id).execute()
        else:
            result = self.db.table("carrier_specs").insert(spec_data).execute()

        return {
            "carrier_id": carrier_id,
            "carrier_name": carrier_name,
            "label_rules": label_rules,
            "edi_rules": edi_rules
        }

    async def get_carrier_rules(self, carrier_id: str) -> Dict[str, Any]:
        spec_response = self.db.table("carrier_specs").select("*").eq("carrier_id", carrier_id).maybeSingle().execute()

        if not spec_response.data:
            return {"label_rules": {}, "edi_rules": {}}

        return {
            "label_rules": spec_response.data.get("label_rules", {}),
            "edi_rules": spec_response.data.get("edi_rules", {})
        }
