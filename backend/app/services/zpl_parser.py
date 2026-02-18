import re
from typing import Dict, Any


def parse_zpl_script(script: str) -> Dict[str, Any]:
    parsed = {}

    # --------------------------------------
    # Extract all ^FD content blocks
    # --------------------------------------
    fd_blocks = re.findall(r"\^FD(.*?)\^FS", script, re.DOTALL)

    clean_blocks = [block.strip() for block in fd_blocks if block.strip()]

    # --------------------------------------
    # Tracking Number (DHL style example)
    # --------------------------------------
    tracking_pattern = r"\b[A-Z]{2}\d{18,22}\b"

    for block in clean_blocks:
        match = re.search(tracking_pattern, block)
        if match:
            parsed["tracking_number"] = match.group(0)
            parsed["barcode"] = match.group(0)
            break

    # --------------------------------------
    # Postal Code (5 digit or 5+4)
    # --------------------------------------
    postal_pattern = r"\b\d{5}(-\d{4})?\b"

    for block in clean_blocks:
        match = re.search(postal_pattern, block)
        if match:
            parsed["postal_code"] = match.group(0)
            break

    # --------------------------------------
    # Weight Extraction
    # --------------------------------------
    weight_pattern = r"\b\d+(\.\d+)?\s?(KG|LB|kg|lb)\b"

    for block in clean_blocks:
        match = re.search(weight_pattern, block)
        if match:
            parsed["weight"] = match.group(0)
            break

    # --------------------------------------
    # Detect Address Blocks (basic grouping)
    # --------------------------------------
    address_blocks = []
    temp_block = []

    for block in clean_blocks:
        if len(block.split()) >= 2:
            temp_block.append(block)
        else:
            if len(temp_block) >= 3:
                address_blocks.append(temp_block)
            temp_block = []

    if len(temp_block) >= 3:
        address_blocks.append(temp_block)

    if len(address_blocks) >= 1:
        parsed["sender_block"] = address_blocks[0]

    if len(address_blocks) >= 2:
        parsed["recipient_block"] = address_blocks[1]

    return parsed
