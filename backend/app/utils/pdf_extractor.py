import pdfplumber
from typing import Dict, Any, Tuple
import re


# ---------------------------------------------------
# 1️⃣ Structured PDF Extraction
# ---------------------------------------------------
def extract_structured_pdf_data(pdf_path: str) -> Dict[str, Any]:
    raw_text = ""
    text_blocks = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            raw_text += page_text + "\n"

            words = page.extract_words()
            for word in words:
                text_blocks.append({
                    "text": word["text"],
                    "bbox": [word["x0"], word["top"], word["x1"], word["bottom"]]
                })

    is_text_based = len(raw_text.strip()) > 50

    return {
        "raw_text": raw_text,
        "text_blocks": text_blocks,
        "metadata": {
            "is_text_based": is_text_based
        }
    }


# ---------------------------------------------------
# 2️⃣ Intelligent Rule Generator
# ---------------------------------------------------
def generate_rule_template_from_spec(
    spec_data: Dict[str, Any],
    spec_type: str
) -> Tuple[Dict[str, Any], float]:

    raw_text = spec_data.get("raw_text", "")
    text_blocks = spec_data.get("text_blocks", [])
    raw_text_upper = raw_text.upper()

    rules: Dict[str, Any] = {
        "required_fields": [],
        "field_formats": {},
        "layout_constraints": {},
        "validation_patterns": {}
    }

    # Scoring buckets
    field_score = 0
    pattern_score = 0
    layout_score = 0

    # ---------------------------------------------------
    # LABEL SPEC PROCESSING
    # ---------------------------------------------------
    if spec_type == "label":

        # -----------------------------
        # 1️⃣ Tracking Number Detection
        # -----------------------------
        tracking_regex = re.search(
            r"tracking\s*number.*?(\d{1,2})\s*[-to]{0,3}\s*(\d{1,2})?\s*(alphanumeric|numeric)?",
            raw_text,
            re.IGNORECASE
        )

        if tracking_regex:
            min_len = tracking_regex.group(1)
            max_len = tracking_regex.group(2) or min_len

            rules["field_formats"]["tracking_number"] = {
                "pattern": f"^[A-Z0-9]{{{min_len},{max_len}}}$",
                "required": True
            }

            rules["required_fields"].append("tracking_number")

            field_score += 1
            pattern_score += 1


        # -----------------------------
        # 2️⃣ Barcode Detection
        # -----------------------------
        barcode_types = ["CODE128", "QR", "PDF417", "DATAMATRIX"]

        for barcode in barcode_types:
            if barcode in raw_text_upper:
                rules["field_formats"]["barcode"] = {
                    "format": barcode,
                    "required": True
                }
                rules["required_fields"].append("barcode")

                field_score += 1
                pattern_score += 1
                break


        # -----------------------------
        # 3️⃣ Postal Code Detection
        # -----------------------------
        if "POSTAL" in raw_text_upper or "ZIP" in raw_text_upper:
            rules["field_formats"]["postal_code"] = {
                "pattern": r"^\d{5}(-\d{4})?$",
                "required": True
            }

            rules["required_fields"].append("postal_code")

            field_score += 1
            pattern_score += 1


        # -----------------------------
        # 4️⃣ Layout Size Detection
        # -----------------------------
        size_match = re.search(
            r"(\d)\s*[xX]\s*(\d)",
            raw_text
        )

        if size_match:
            width = int(size_match.group(1))
            height = int(size_match.group(2))

            rules["layout_constraints"] = {
                "label_width": width,
                "label_height": height,
                "units": "inches"
            }

            layout_score += 1


        # -----------------------------
        # 5️⃣ Layout Density Heuristic
        # -----------------------------
        if len(text_blocks) > 20:
            layout_score += 0.5


        # -----------------------------
        # Confidence Calculation
        # -----------------------------
        max_field_score = 3
        max_pattern_score = 3
        max_layout_score = 1.5

        field_conf = field_score / max_field_score
        pattern_conf = pattern_score / max_pattern_score
        layout_conf = layout_score / max_layout_score

        confidence_score = (
            0.4 * field_conf +
            0.4 * pattern_conf +
            0.2 * layout_conf
        )

        confidence_score = round(min(confidence_score, 1.0), 2)


    # ---------------------------------------------------
    # EDI SPEC PROCESSING
    # ---------------------------------------------------
    elif spec_type == "edi":

        rules["required_segments"] = []
        segments = ["ISA", "GS", "ST", "SE", "GE", "IEA"]

        for seg in segments:
            if seg in raw_text_upper:
                rules["required_segments"].append(seg)

        rules["segment_order"] = rules["required_segments"] or segments

        rules["delimiter_rules"] = {
            "segment_delimiter": "~",
            "element_delimiter": "*",
            "sub_element_delimiter": ":"
        }

        confidence_score = len(rules["required_segments"]) / len(segments)
        confidence_score = round(min(confidence_score, 1.0), 2)

    else:
        confidence_score = 0.0

    return rules, confidence_score
