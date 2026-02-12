import pdfplumber
from typing import Dict, Any, List


def extract_text_from_pdf(pdf_path: str) -> str:
    text_content = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_content += page.extract_text() or ""
    return text_content


def generate_rule_template_from_spec(spec_text: str, spec_type: str) -> Dict[str, Any]:
    rules = {
        "required_fields": [],
        "field_formats": {},
        "layout_constraints": {},
        "validation_patterns": {}
    }

    if spec_type == "label":
        rules["required_fields"] = ["tracking_number", "barcode", "sender_address", "recipient_address"]
        rules["field_formats"] = {
            "tracking_number": {"pattern": r"^[A-Z0-9]{10,20}$", "required": True},
            "barcode": {"format": "CODE128", "required": True},
            "postal_code": {"pattern": r"^\d{5}(-\d{4})?$", "required": True}
        }
        rules["layout_constraints"] = {
            "label_width": 4,
            "label_height": 6,
            "dpi": 203,
            "units": "inches"
        }

    elif spec_type == "edi":
        rules["required_segments"] = []
        rules["segment_order"] = []
        rules["field_formats"] = {}

        lines = spec_text.split('\n')
        for line in lines:
            line_upper = line.upper()
            if 'ISA' in line_upper:
                rules["required_segments"].append("ISA")
            if 'GS' in line_upper:
                rules["required_segments"].append("GS")
            if 'ST' in line_upper:
                rules["required_segments"].append("ST")
            if 'BSN' in line_upper or 'B10' in line_upper:
                rules["required_segments"].append("BSN")
            if 'SE' in line_upper:
                rules["required_segments"].append("SE")
            if 'GE' in line_upper:
                rules["required_segments"].append("GE")
            if 'IEA' in line_upper:
                rules["required_segments"].append("IEA")

        if rules["required_segments"]:
            rules["segment_order"] = rules["required_segments"]
        else:
            rules["required_segments"] = ["ISA", "GS", "ST", "SE", "GE", "IEA"]
            rules["segment_order"] = ["ISA", "GS", "ST", "SE", "GE", "IEA"]

        rules["delimiter_rules"] = {
            "segment_delimiter": "~",
            "element_delimiter": "*",
            "sub_element_delimiter": ":"
        }

    return rules
