import re
import cv2
import numpy as np
import pytesseract
from typing import Dict, Any, List
from app.models.validation import ValidationError

try:
    from pyzbar import pyzbar
except Exception:
    pyzbar = None


class LabelValidator:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules

    # ===============================
    # MAIN VALIDATION ENTRY
    # ===============================

    async def validate(self, label_data: bytes, is_zpl: bool = False) -> Dict[str, Any]:
        errors: List[ValidationError] = []

        img = self._load_image(label_data)
        if img is None:
            return self._fail_response("Unreadable image file.")

        text_content = self._extract_text(img)
        barcodes = self._detect_barcodes(img)
        layout_blocks = self._detect_layout_blocks(img)

        field_errors, field_score = self._validate_fields(text_content, barcodes)
        barcode_errors, barcode_score = self._validate_barcode(barcodes)
        layout_errors, layout_score = self._validate_layout(layout_blocks)

        errors.extend(field_errors)
        errors.extend(barcode_errors)
        errors.extend(layout_errors)

        compliance_score = field_score + barcode_score + layout_score
        compliance_score = round(min(compliance_score, 1.0), 2)

        status = "PASS" if not errors else "FAIL"

        return {
            "status": status,
            "errors": [e.dict() for e in errors],
            "corrected_label_script": None,
            "compliance_score": compliance_score
        }

    # ===============================
    # IMAGE UTILITIES
    # ===============================

    def _load_image(self, image_data: bytes):
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def _extract_text(self, img) -> str:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return pytesseract.image_to_string(gray)

    def _detect_barcodes(self, img):
        if pyzbar is None:
            return []

        try:
            detected = []
            for barcode in pyzbar.decode(img):
                detected.append({
                    "type": barcode.type,
                    "data": barcode.data.decode("utf-8")
                })
            return detected
        except Exception:
            return []

    def _detect_layout_blocks(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        blocks = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 20 and h > 20:
                blocks.append((x, y, w, h))
        return blocks

    # ===============================
    # FIELD VALIDATION
    # ===============================

    def _validate_fields(self, text: str, barcodes: list):
        errors = []
        score = 0.0

        fields = self.rules.get("fields", {})

        for field_name, rule in fields.items():
            weight = rule.get("weight", 0.1)

            if field_name == "tracking_number":
                matched = False

                # Validate via barcode if required
                if rule.get("must_match_barcode") and barcodes:
                    barcode_value = barcodes[0]["data"]
                    if re.match(rule["pattern"], barcode_value):
                        matched = True

                # Also check OCR text
                if not matched:
                    if re.search(rule["pattern"], text):
                        matched = True

                if not matched and rule.get("required"):
                    errors.append(ValidationError(
                        field="tracking_number",
                        expected="Valid tracking number format",
                        actual="Not found or invalid format",
                        description="Tracking number missing or invalid."
                    ))
                else:
                    score += weight

            elif field_name in ["sender_block", "recipient_block"]:
                min_lines = rule.get("min_lines", 3)
                blocks = text.split("\n\n")

                valid_block = False
                for block in blocks:
                    lines = [l for l in block.split("\n") if l.strip()]
                    if len(lines) >= min_lines:
                        valid_block = True
                        break

                if not valid_block and rule.get("required"):
                    errors.append(ValidationError(
                        field=field_name,
                        expected=f"Block with at least {min_lines} lines",
                        actual="Block not found",
                        description=f"{field_name} structure invalid."
                    ))
                else:
                    score += weight

            else:
                pattern = rule.get("pattern")
                if pattern and re.search(pattern, text):
                    score += weight
                elif rule.get("required"):
                    errors.append(ValidationError(
                        field=field_name,
                        expected="Pattern match",
                        actual="Not found",
                        description=f"{field_name} missing."
                    ))

        return errors, score

    # ===============================
    # BARCODE VALIDATION
    # ===============================

    def _validate_barcode(self, barcodes):
        errors = []
        score = 0.0

        rule = self.rules.get("barcode", {})
        weight = rule.get("weight", 0.1)

        if rule.get("required") and not barcodes:
            errors.append(ValidationError(
                field="barcode",
                expected="At least one barcode",
                actual="None detected",
                description="Barcode missing."
            ))
        else:
            score += weight

        return errors, score

    # ===============================
    # LAYOUT VALIDATION
    # ===============================

    def _validate_layout(self, layout_blocks):
        errors = []
        score = 0.0

        rule = self.rules.get("layout", {})
        weight = rule.get("weight", 0.05)

        min_blocks = rule.get("min_blocks", 0)

        if len(layout_blocks) < min_blocks:
            errors.append(ValidationError(
                field="layout",
                expected=f"At least {min_blocks} layout blocks",
                actual=f"{len(layout_blocks)} detected",
                description="Label layout incomplete."
            ))
        else:
            score += weight

        return errors, score

    # ===============================
    # FAILURE RESPONSE
    # ===============================

    def _fail_response(self, message):
        return {
            "status": "FAIL",
            "errors": [{
                "field": "file",
                "expected": "Valid image",
                "actual": "Unreadable file",
                "description": message
            }],
            "corrected_label_script": None,
            "compliance_score": 0.0
        }
