import cv2
import numpy as np
import pytesseract
from pyzbar import pyzbar
from PIL import Image
import httpx
from typing import Dict, Any, List, Tuple
from app.models.validation import ValidationError
from app.config import get_settings

settings = get_settings()


class LabelValidator:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules

    async def render_zpl_to_image(self, zpl_content: str) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.labelary_api_url,
                content=zpl_content,
                headers={"Accept": "image/png"}
            )
            if response.status_code == 200:
                return response.content
            raise Exception(f"Failed to render ZPL: {response.text}")

    def load_image(self, image_data: bytes) -> np.ndarray:
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def extract_text_from_image(self, img: np.ndarray) -> str:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)
        return text

    def detect_barcodes(self, img: np.ndarray) -> List[Dict[str, str]]:
        barcodes = pyzbar.decode(img)
        detected = []
        for barcode in barcodes:
            detected.append({
                "type": barcode.type,
                "data": barcode.data.decode("utf-8")
            })
        return detected

    def detect_layout_blocks(self, img: np.ndarray) -> List[Tuple[int, int, int, int]]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        blocks = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 20 and h > 20:
                blocks.append((x, y, w, h))

        return blocks

    async def validate(self, label_data: bytes, is_zpl: bool = False) -> Dict[str, Any]:
        errors = []

        if is_zpl:
            try:
                image_data = await self.render_zpl_to_image(label_data.decode("utf-8"))
                img = self.load_image(image_data)
            except Exception as e:
                errors.append(ValidationError(
                    field="zpl_rendering",
                    expected="Valid ZPL that can be rendered",
                    actual="Failed to render",
                    description=f"ZPL rendering failed: {str(e)}"
                ))
                return {
                    "status": "FAIL",
                    "errors": [e.dict() for e in errors],
                    "corrected_label_script": None,
                    "compliance_score": 0.0
                }
        else:
            img = self.load_image(label_data)

        text_content = self.extract_text_from_image(img)
        barcodes = self.detect_barcodes(img)
        layout_blocks = self.detect_layout_blocks(img)

        required_fields = self.rules.get("required_fields", [])
        field_formats = self.rules.get("field_formats", {})

        for field in required_fields:
            if field == "barcode":
                if not barcodes:
                    errors.append(ValidationError(
                        field="barcode",
                        expected="At least one barcode present",
                        actual="No barcode detected",
                        description="Label must contain a barcode"
                    ))
            elif field not in text_content.lower():
                errors.append(ValidationError(
                    field=field,
                    expected=f"Field '{field}' present in label",
                    actual="Field not found",
                    description=f"Required field '{field}' is missing from label"
                ))

        if len(layout_blocks) < 3:
            errors.append(ValidationError(
                field="layout",
                expected="At least 3 distinct layout blocks",
                actual=f"Only {len(layout_blocks)} blocks detected",
                description="Label layout appears incomplete"
            ))

        compliance_score = max(0.0, 1.0 - (len(errors) / max(len(required_fields), 1)))

        status = "PASS" if len(errors) == 0 else "FAIL"

        corrected_script = None
        if is_zpl and errors:
            corrected_script = self.generate_corrected_zpl(label_data.decode("utf-8"), errors)

        return {
            "status": status,
            "errors": [e.dict() for e in errors],
            "corrected_label_script": corrected_script,
            "compliance_score": compliance_score
        }

    def generate_corrected_zpl(self, original_zpl: str, errors: List[ValidationError]) -> str:
        corrected = original_zpl

        if any(e.field == "barcode" for e in errors):
            if "^BY" not in corrected:
                corrected = corrected.replace("^XA", "^XA\n^BY2,3,100")
            if "^BC" not in corrected:
                corrected = corrected.replace("^XA", "^XA\n^FO50,50^BCN,100,Y,N,N^FD123456789^FS")

        return corrected
