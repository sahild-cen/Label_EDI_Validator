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

    # =====================================================
    # MAIN VALIDATION ENTRY
    # =====================================================

    async def validate(self, label_data: bytes, is_zpl: bool = False) -> Dict[str, Any]:
        errors: List[ValidationError] = []

        parsed_data = {}
        original_script = ""
        barcodes = []
        layout_blocks = []

        # -----------------------------------
        # ZPL FILE
        # -----------------------------------
        if is_zpl:
            original_script = label_data.decode("utf-8")

            from app.services.zpl_parser import parse_zpl_script
            parsed_data = parse_zpl_script(original_script)

        # -----------------------------------
        # IMAGE / PDF FILE
        # -----------------------------------
        else:
            img = self._load_image(label_data)
            if img is None:
                return self._fail_response("Unreadable image file.")

            text_content = self._extract_text(img)
            parsed_data = self._parse_ocr_text(text_content)

            barcodes = self.detect_barcodes(img)
            layout_blocks = self.detect_layout_blocks(img)

        # -----------------------------------
        # VALIDATIONS
        # -----------------------------------
        field_errors, field_score, field_total = self._validate_fields(parsed_data)
        barcode_errors, barcode_score, barcode_total = self._validate_barcode(barcodes, parsed_data)
        layout_errors, layout_score, layout_total = self._validate_layout(layout_blocks)

        errors.extend(field_errors)
        errors.extend(barcode_errors)
        errors.extend(layout_errors)

        total_possible = field_total + barcode_total + layout_total
        total_earned = field_score + barcode_score + layout_score

        compliance_score = round(total_earned / total_possible, 2) if total_possible > 0 else 0.0

        status = "PASS" if not errors else "FAIL"

        # -----------------------------------
        # AUTO CORRECTION (ZPL ONLY)
        # -----------------------------------
        corrected_script = None
        if is_zpl and errors:
            corrected_script = self._auto_correct_zpl(
                original_script=original_script,
                parsed_data=parsed_data,
                errors=errors
            )

        return {
            "status": status,
            "errors": [e.dict() for e in errors],
            "corrected_label_script": corrected_script,
            "compliance_score": compliance_score
        }

    # =====================================================
    # IMAGE UTILITIES
    # =====================================================

    def _load_image(self, image_data: bytes):
        nparr = np.frombuffer(image_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def _extract_text(self, img) -> str:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        return pytesseract.image_to_string(gray)

    def _parse_ocr_text(self, text: str) -> Dict[str, str]:
        parsed = {}

        # Simple extraction patterns (improve gradually)
        tracking_match = re.search(r"\b\d{10,20}\b", text)
        if tracking_match:
            parsed["tracking_number"] = tracking_match.group()

        postal_match = re.search(r"\b\d{5}(-\d{4})?\b", text)
        if postal_match:
            parsed["postal_code"] = postal_match.group()

        weight_match = re.search(r"\b\d+(\.\d+)?\s?(KG|LB)\b", text, re.IGNORECASE)
        if weight_match:
            parsed["weight"] = weight_match.group()

        return parsed

    # =====================================================
    # FIELD VALIDATION (SPEC-DRIVEN)
    # =====================================================

    def _validate_fields(self, parsed_data: dict):
        errors = []
        earned = 0.0
        total = 0.0

        field_formats = {
            k: v for k, v in self.rules.get("field_formats", {}).items()
            if k != "barcode"
        }


        for field_name, rule in field_formats.items():
            weight = 0.1
            total += weight

            required = rule.get("required", False)
            pattern = rule.get("pattern")

            value = parsed_data.get(field_name)

            passed = False

            if value and pattern:
                if re.match(pattern, value):
                    passed = True

            if passed:
                earned += weight
            elif required:
                errors.append(ValidationError(
                    field=field_name,
                    expected=f"Pattern: {pattern}",
                    actual=value if value else "Not found",
                    description=f"{field_name} validation failed."
                ))

        return errors, earned, total

    # =====================================================
    # BARCODE VALIDATION
    # =====================================================

    def _validate_barcode(self, barcodes, parsed_data):
        errors = []
        earned = 0.0
        total = 0.1

        barcode_rule = self.rules.get("field_formats", {}).get("barcode", {})
        required = barcode_rule.get("required", False)
        pattern = barcode_rule.get("pattern")

        zpl_barcode = parsed_data.get("barcode")

        value = None

        if zpl_barcode:
            value = zpl_barcode
        elif barcodes:
            value = barcodes[0]["data"]

        passed = False

        if value:
            if pattern:
                if re.match(pattern, value):
                    passed = True
            else:
                passed = True  # no pattern rule → just existence

        if required and not passed:
            errors.append(ValidationError(
                field="barcode",
                expected=f"Pattern: {pattern}" if pattern else "At least one barcode",
                actual=value if value else "Not found",
                description="barcode validation failed."
            ))
        else:
            earned += 0.1

        return errors, earned, total


    # =====================================================
    # LAYOUT VALIDATION
    # =====================================================

    def _validate_layout(self, layout_blocks):
        errors = []
        earned = 0.0
        total = 0.05

        layout_rules = self.rules.get("layout_constraints", {})
        min_blocks = layout_rules.get("min_blocks", 0)

        if min_blocks and len(layout_blocks) < min_blocks:
            errors.append(ValidationError(
                field="layout",
                expected=f"At least {min_blocks} layout blocks",
                actual=f"{len(layout_blocks)} detected",
                description="Label layout incomplete."
            ))
        else:
            earned += 0.05

        return errors, earned, total

    # =====================================================
    # SMART AUTO CORRECTION (NO HARDCODE TEMPLATE)
    # =====================================================

    def _auto_correct_zpl(self, original_script: str, parsed_data: dict, errors: list):
        corrected = original_script.strip()

        additions = []

        for error in errors:
            field = error.field

            if field == "postal_code":
                additions.append("^FO50,750^FD 12345 ^FS")

            elif field == "tracking_number":
                additions.append("^FO50,780^FD 123456789012 ^FS")

            elif field == "weight":
                additions.append("^FO50,810^FD 1 KG ^FS")

            elif field == "barcode":
                additions.append("^BY3,3,120\n^FD123456789012^FS")

        if additions:
            corrected = corrected.replace("^XZ", "")
            corrected += "\n" + "\n".join(additions) + "\n^XZ"

        return corrected


    # =====================================================
    # FAILURE RESPONSE
    # =====================================================

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
