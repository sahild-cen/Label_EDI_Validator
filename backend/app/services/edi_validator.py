import re
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from app.models.validation import ValidationError


class EDIValidator:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules

    def detect_format(self, content: str) -> str:
        content_stripped = content.strip()

        if content_stripped.startswith('{') or content_stripped.startswith('['):
            try:
                json.loads(content)
                return "json"
            except:
                pass

        if content_stripped.startswith('<'):
            try:
                ET.fromstring(content)
                return "xml"
            except:
                pass

        if '~' in content and '*' in content:
            return "x12"

        if "'" in content and '+' in content:
            return "edifact"

        if '\n' in content and len(content.split('\n')) > 1:
            return "delimited"

        return "fixed_width"

    def parse_content(self, content: str, format_type: str) -> Dict[str, Any]:
        if format_type == "json":
            return json.loads(content)

        elif format_type == "xml":
            root = ET.fromstring(content)
            return self._xml_to_dict(root)

        elif format_type in ["x12", "edifact"]:
            return self._parse_edi_segments(content, format_type)

        elif format_type == "delimited":
            lines = content.strip().split('\n')
            return {"lines": lines, "segments": [line.split('|') for line in lines]}

        else:
            return {"raw_content": content}

    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        result = {}
        for child in element:
            result[child.tag] = child.text or self._xml_to_dict(child)
        return result

    def _parse_edi_segments(self, content: str, format_type: str) -> Dict[str, Any]:
        if format_type == "x12":
            segment_delimiter = '~'
            element_delimiter = '*'
        else:
            segment_delimiter = "'"
            element_delimiter = '+'

        segments = content.split(segment_delimiter)
        parsed_segments = []

        for segment in segments:
            segment = segment.strip()
            if segment:
                elements = segment.split(element_delimiter)
                parsed_segments.append({
                    "segment_id": elements[0] if elements else "",
                    "elements": elements
                })

        return {
            "format": format_type,
            "segments": parsed_segments
        }

    async def validate(self, edi_content: str) -> Dict[str, Any]:
        errors = []

        format_type = self.detect_format(edi_content)

        try:
            parsed_data = self.parse_content(edi_content, format_type)
        except Exception as e:
            errors.append(ValidationError(
                field="parsing",
                expected=f"Valid {format_type} format",
                actual="Parse error",
                description=f"Failed to parse EDI content: {str(e)}"
            ))
            return {
                "status": "FAIL",
                "errors": [e.dict() for e in errors],
                "corrected_edi_script": None,
                "compliance_score": 0.0
            }

        required_segments = self.rules.get("required_segments", [])
        segment_order = self.rules.get("segment_order", [])

        if format_type in ["x12", "edifact"]:
            segments = parsed_data.get("segments", [])
            segment_ids = [seg["segment_id"] for seg in segments]

            for required_seg in required_segments:
                if required_seg not in segment_ids:
                    errors.append(ValidationError(
                        field="segments",
                        expected=f"Segment '{required_seg}' present",
                        actual="Segment missing",
                        description=f"Required segment '{required_seg}' is missing"
                    ))

            if segment_order:
                expected_order_indices = []
                actual_order_indices = []

                for seg in segment_order:
                    if seg in segment_ids:
                        expected_order_indices.append(segment_order.index(seg))
                        actual_order_indices.append(segment_ids.index(seg))

                if actual_order_indices != sorted(actual_order_indices):
                    errors.append(ValidationError(
                        field="segment_order",
                        expected=f"Segments in order: {', '.join(segment_order)}",
                        actual=f"Actual order: {', '.join(segment_ids[:5])}...",
                        description="Segments are not in the correct order"
                    ))

        elif format_type == "json":
            required_fields = self.rules.get("required_fields", [])
            for field in required_fields:
                if field not in parsed_data:
                    errors.append(ValidationError(
                        field=field,
                        expected=f"Field '{field}' present",
                        actual="Field missing",
                        description=f"Required field '{field}' is missing"
                    ))

        compliance_score = max(0.0, 1.0 - (len(errors) / max(len(required_segments or []) + 2, 1)))

        status = "PASS" if len(errors) == 0 else "FAIL"

        corrected_script = None
        if errors:
            corrected_script = self.generate_corrected_edi(edi_content, format_type, errors, parsed_data)

        return {
            "status": status,
            "errors": [e.dict() for e in errors],
            "corrected_edi_script": corrected_script,
            "compliance_score": compliance_score
        }

    def generate_corrected_edi(
        self,
        original_content: str,
        format_type: str,
        errors: List[ValidationError],
        parsed_data: Dict[str, Any]
    ) -> str:
        if format_type in ["x12", "edifact"]:
            delimiter = '~' if format_type == "x12" else "'"
            element_delim = '*' if format_type == "x12" else '+'

            segments = parsed_data.get("segments", [])
            segment_ids = [seg["segment_id"] for seg in segments]

            missing_segments = []
            for error in errors:
                if error.field == "segments" and "missing" in error.description.lower():
                    seg_name = error.expected.split("'")[1] if "'" in error.expected else ""
                    if seg_name and seg_name not in segment_ids:
                        missing_segments.append(seg_name)

            corrected_segments = []
            for seg in segments:
                corrected_segments.append(element_delim.join(seg["elements"]))

            for missing_seg in missing_segments:
                if missing_seg == "ISA":
                    corrected_segments.insert(0, f"ISA{element_delim}00{element_delim}          {element_delim}00")
                elif missing_seg == "GS":
                    corrected_segments.insert(1, f"GS{element_delim}PO{element_delim}SENDER{element_delim}RECEIVER")
                elif missing_seg == "ST":
                    corrected_segments.insert(2, f"ST{element_delim}850{element_delim}0001")
                elif missing_seg == "SE":
                    corrected_segments.append(f"SE{element_delim}10{element_delim}0001")
                elif missing_seg == "GE":
                    corrected_segments.append(f"GE{element_delim}1{element_delim}1")
                elif missing_seg == "IEA":
                    corrected_segments.append(f"IEA{element_delim}1{element_delim}000000001")

            return delimiter.join(corrected_segments) + delimiter

        return original_content
