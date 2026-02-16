import fitz  # PyMuPDF

def convert_pdf_to_image_bytes(path: str) -> bytes:
    doc = fitz.open(path)
    page = doc[0]  # First page (shipping labels usually single page)
    pix = page.get_pixmap(dpi=300)  # High resolution for OCR
    return pix.tobytes("png")
