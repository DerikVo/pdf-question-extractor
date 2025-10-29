!apt-get install -y tesseract-ocr > /dev/null
!pip install PyMuPDF Pillow pytesseract -q

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance
from pathlib import Path
import io
from google.colab import files
import re


class FinalOCRProcessor:
    def __init__(self, input_pdf: str):
        self.input_pdf = input_pdf
        self.doc = fitz.open(input_pdf)

    def extract_text_with_ocr(self, page_num: int):
        """Extract text from PDF page using OCR"""
        page = self.doc[page_num]

        # Convert page to image with high DPI for better OCR
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Enhance image for better OCR
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)

        # Use OCR to extract text with bounding boxes
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        return ocr_data, img.size, page.rect

    def detect_questions_with_ocr(self, page_num: int):
        """Use OCR to detect question regions accurately"""
        ocr_data, img_size, page_rect = self.extract_text_with_ocr(page_num)

        # Convert image coordinates to PDF coordinates
        page = self.doc[page_num]
        scale_x = page_rect.width / img_size[0]
        scale_y = page_rect.height / img_size[1]

        # Find question numbers and their positions
        questions = []
        for i, text in enumerate(ocr_data['text']):
            text = text.strip()
            if text and text[0].isdigit() and any(marker in text for marker in ['.', ')']):
                # Found a question number
                x = ocr_data['left'][i] * scale_x
                y = ocr_data['top'][i] * scale_y
                width = ocr_data['width'][i] * scale_x
                height = ocr_data['height'][i] * scale_y

                questions.append({
                    'number': text.split('.')[0] if '.' in text else text.split(')')[0],
                    'text': text,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'index': i
                })

        print(f"OCR detected {len(questions)} questions")

        # Sort questions by y-position
        questions.sort(key=lambda q: q['y'])

        # DYNAMIC MARGIN DETECTION
        if questions:
            min_question_x = min(q['x'] for q in questions)
            left_margin = max(5, min_question_x - 25)
        else:
            left_margin = 30

        # Create regions for each question
        regions = []
        for i, q in enumerate(questions):
            start_y = max(5, q['y'] - 7)

            if i + 1 < len(questions):
                end_y = questions[i + 1]['y'] - 15
            else:
                end_y = page_rect.height - 25

            end_y = min(end_y, page_rect.height - 10)
            right_margin = 30

            regions.append((left_margin, start_y, page_rect.width - right_margin, end_y))

        return regions, questions

    def calculate_scaling(self, crop_rect, enlarge_factor=1.0):
        """Calculate scaling based on user's enlargement factor"""
        crop_width = crop_rect.width
        crop_height = crop_rect.height

        print(f"Original crop: {crop_width:.1f} x {crop_height:.1f}")

        # Target page dimensions (landscape)
        target_width = 792
        target_height = 612

        # Minimal margins to prevent cutting
        margin = 20

        # Calculate maximum possible content area
        max_content_width = target_width - (2 * margin)
        max_content_height = target_height - (2 * margin)

        # Calculate base scale to fit content
        scale_x = max_content_width / crop_width
        scale_y = max_content_height / crop_height

        # Use the smaller scale as base
        base_scale = min(scale_x, scale_y)

        # Apply user's enlargement factor
        final_scale = base_scale * enlarge_factor

        print(f"Base scale: {base_scale:.2f}x, Final scale: {final_scale:.2f}x (enlargement: {enlarge_factor}x)")

        return final_scale, margin

    def create_final_question_pages(self, page_num: int, output_pdf: str = "final_questions.pdf", enlarge_factor=1.25):
        """Create question pages with user-controlled enlargement"""
        # Get regions using OCR
        regions, questions = self.detect_questions_with_ocr(page_num)

        if not regions:
            print("No questions detected via OCR. Using fallback method.")
            regions = self._create_fallback_regions(page_num)

        # Create output document
        output_doc = fitz.open()

        print(f"Creating pages with {enlarge_factor}x enlargement...")

        for i, region in enumerate(regions, 1):
            print(f"Processing question {i}...")

            # Create landscape page
            new_page = output_doc.new_page(width=792, height=612)

            # Define crop rectangle
            crop_rect = fitz.Rect(region)

            # Calculate scaling
            scale, margin = self.calculate_scaling(crop_rect, enlarge_factor)

            # Calculate scaled dimensions
            scaled_width = crop_rect.width * scale
            scaled_height = crop_rect.height * scale

            # Center the content
            x_offset = (792 - scaled_width) / 2
            y_offset = (612 - scaled_height) / 2

            target_rect = fitz.Rect(
                x_offset,
                y_offset,
                x_offset + scaled_width,
                y_offset + scaled_height
            )

            # Copy content to new page
            new_page.show_pdf_page(target_rect, self.doc, page_num, clip=crop_rect)

            print(f"Created page {i} (scale: {scale:.2f}x)")

        # Save with meaningful filename
        if output_pdf == "final_questions.pdf":
            output_pdf = f"final_questions_{enlarge_factor}x.pdf"

        output_doc.save(output_pdf, garbage=4, deflate=True)
        output_doc.close()

        file_size = Path(output_pdf).stat().st_size / (1024 * 1024)
        print(f"\nProcessing complete!")
        print(f"Output: {output_pdf} ({file_size:.1f} MB)")
        print(f"Enlargement factor: {enlarge_factor}x")

        return output_pdf

    def _create_fallback_regions(self, page_num: int):
        """Simple fallback regions"""
        page = self.doc[page_num]
        page_height = page.rect.height
        page_width = page.rect.width

        # Split into 5 equal regions
        num_regions = 5
        region_height = page_height / num_regions
        regions = []

        for i in range(num_regions):
            y_start = i * region_height
            y_end = (i + 1) * region_height
            regions.append((25, y_start, page_width - 25, y_end))

        print(f"Fallback: Using {num_regions} regions")
        return regions

    def close(self):
        self.doc.close()

# =============================================================================
# SINGLE SIMPLE FUNCTION
# =============================================================================

def final_process_safe(page_number=22, enlarge_factor=8.0):
    """Final processing with enlargement control

    Args:
        page_number: Page number to process (1-indexed)
        enlarge_factor: How much to enlarge questions (1.0 = normal, 8.0 = 8x larger)
    """
    print("Upload your PDF file...")
    uploaded = files.upload()

    if not uploaded:
        print("No file uploaded!")
        return

    pdf_filename = list(uploaded.keys())[0]
    print(f"Uploaded: {pdf_filename}")

    processor = FinalOCRProcessor(pdf_filename)

    print(f"\nPROCESSING SETTINGS:")
    print(f"   Page: {page_number}")
    print(f"   Enlarge factor: {enlarge_factor}x")
    print("=" * 50)

    output_file = processor.create_final_question_pages(
        page_number - 1,
        enlarge_factor=enlarge_factor
    )

    print(f"\nDownloading {output_file}...")
    files.download(output_file)

    processor.close()
    return output_file