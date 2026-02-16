import re
import cv2
import numpy as np
import pytesseract
from typing import Dict, Any, List
from app.models.validation import ValidationError

# 🔥 ADD THIS
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\sahild\AppData\Local\Programs\Tesseract-OCR"


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

        field_errors, field_earned, field_total, field_breakdown = self._validate_fields(text_content, barcodes)
        barcode_errors, barcode_earned, barcode_total, barcode_breakdown = self._validate_barcode(barcodes)
        layout_errors, layout_earned, layout_total, layout_breakdown = self._validate_layout(layout_blocks)


        errors.extend(field_errors)
        errors.extend(barcode_errors)
        errors.extend(layout_errors)

        total_possible = field_total + barcode_total + layout_total
        total_earned = field_earned + barcode_earned + layout_earned

        if total_possible > 0:
            compliance_score = round(total_earned / total_possible, 2)
        else:
            compliance_score = 0.0

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
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

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
        earned_weight = 0.0
        total_weight = 0.0
        breakdown = {}

        fields = self.rules.get("fields", {})

        for field_name, rule in fields.items():
            weight = rule.get("weight", 0.1)
            total_weight += weight

            matched = False

            if field_name == "tracking_number":
                if rule.get("must_match_barcode") and barcodes:
                    barcode_value = barcodes[0]["data"]
                    if re.match(rule.get("pattern", ""), barcode_value):
                        matched = True

                if not matched and re.search(rule.get("pattern", ""), text):
                    matched = True

            elif field_name in ["sender_block", "recipient_block"]:
                min_lines = rule.get("min_lines", 3)
                blocks = text.split("\n\n")

                for block in blocks:
                    lines = [l for l in block.split("\n") if l.strip()]
                    if len(lines) >= min_lines:
                        matched = True
                        break

            else:
                pattern = rule.get("pattern")
                if pattern and re.search(pattern, text):
                    matched = True

            breakdown[field_name] = {
                "passed": matched,
                "weight": weight
            }

            if matched:
                earned_weight += weight
            elif rule.get("required"):
                errors.append(ValidationError(
                    field=field_name,
                    expected="Valid pattern",
                    actual="Not found or invalid",
                    description=f"{field_name} validation failed."
                ))

        return errors, earned_weight, total_weight, breakdown

    # ===============================
    # BARCODE VALIDATION
    # ===============================

    def _validate_barcode(self, barcodes):
        errors = []
        earned_weight = 0.0
        total_weight = 0.0
        breakdown = {}

        rule = self.rules.get("barcode", {})
        weight = rule.get("weight", 0.1)
        total_weight += weight

        passed = True

        if rule.get("required") and not barcodes:
            passed = False
            errors.append(ValidationError(
                field="barcode",
                expected="At least one barcode",
                actual="None detected",
                description="Barcode missing."
            ))
        else:
            earned_weight += weight

        breakdown["barcode"] = {
            "passed": passed,
            "weight": weight
        }

        return errors, earned_weight, total_weight, breakdown


    # ===============================
    # LAYOUT VALIDATION
    # ===============================

    def _validate_layout(self, layout_blocks):
        errors = []
        earned_weight = 0.0
        total_weight = 0.0
        breakdown = {}

        rule = self.rules.get("layout", {})
        weight = rule.get("weight", 0.05)
        total_weight += weight

        min_blocks = rule.get("min_blocks", 0)
        passed = len(layout_blocks) >= min_blocks

        if not passed:
            errors.append(ValidationError(
                field="layout",
                expected=f"At least {min_blocks} layout blocks",
                actual=f"{len(layout_blocks)} detected",
                description="Label layout incomplete."
            ))
        else:
            earned_weight += weight

        breakdown["layout"] = {
            "passed": passed,
            "weight": weight
        }

        return errors, earned_weight, total_weight, breakdown


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
