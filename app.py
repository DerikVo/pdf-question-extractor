import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance
import io
import os

st.set_page_config(
    page_title="PDF Question Extractor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS - works well in both dark and light modes
st.markdown("""
<style>
    :root {
        --primary-color: #007bff;
        --primary-hover: #0056b3;
        --success-color: #28a745;
        --success-hover: #218838;
        --border-radius: 8px;
        --padding: 1rem;
    }

    .main {
        padding: 2rem;
    }

    /* Buttons */
    .stButton>button {
        background-color: var(--primary-color);
        color: white;
        border-radius: var(--border-radius);
        padding: 0.6rem 2rem;
        font-size: 16px;
        border: none;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: var(--primary-hover);
        transform: translateY(-2px);
    }

    /* Info & success boxes - auto adjust for dark mode */
    .info-box, .success-box {
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }

    .info-box {
        background-color: rgba(0, 123, 255, 0.1);
        border-left: 4px solid var(--primary-color);
    }

    .success-box {
        background-color: rgba(40, 167, 69, 0.1);
        border-left: 4px solid var(--success-color);
    }

    /* Download Button */
    .stDownloadButton>button {
        background-color: var(--success-color);
        color: white;
        width: 100%;
        padding: 0.75rem;
        font-size: 16px;
        border-radius: var(--border-radius);
        border: none;
    }
    .stDownloadButton>button:hover {
        background-color: var(--success-hover);
    }

    /* Upload box */
    .upload-section {
        border: 2px dashed #888;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)


# -------------------------------
# OCR Processor
# -------------------------------
class FinalOCRProcessor:
    def __init__(self, input_pdf):
        self.doc = fitz.open(stream=input_pdf, filetype="pdf")

    def extract_text_with_ocr(self, page_num: int):
        page = self.doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        return ocr_data, img.size, page.rect

    def detect_questions_with_ocr(self, page_num: int):
        ocr_data, img_size, page_rect = self.extract_text_with_ocr(page_num)
        scale_x = page_rect.width / img_size[0]
        scale_y = page_rect.height / img_size[1]

        questions = []
        for i, text in enumerate(ocr_data['text']):
            text = text.strip()
            if text and len(text) > 0 and text[0].isdigit() and any(m in text for m in ['.', ')']):
                x = ocr_data['left'][i] * scale_x
                y = ocr_data['top'][i] * scale_y
                width = ocr_data['width'][i] * scale_x
                height = ocr_data['height'][i] * scale_y
                questions.append({
                    'number': text.split('.')[0] if '.' in text else text.split(')')[0],
                    'text': text,
                    'x': x, 'y': y,
                    'width': width, 'height': height
                })

        questions.sort(key=lambda q: q['y'])

        if questions:
            min_question_x = min(q['x'] for q in questions)
            left_margin = max(5, min_question_x - 25)
        else:
            left_margin = 30

        regions = []
        for i, q in enumerate(questions):
            start_y = max(5, q['y'] - 7)
            end_y = questions[i + 1]['y'] - 15 if i + 1 < len(questions) else page_rect.height - 25
            end_y = min(end_y, page_rect.height - 10)
            regions.append((left_margin, start_y, page_rect.width - 30, end_y))

        return regions, questions

    def calculate_scaling(self, crop_rect, enlarge_factor=1.0):
        crop_width = crop_rect.width
        crop_height = crop_rect.height
        target_width = 792
        target_height = 612
        margin = 20
        max_w = target_width - (2 * margin)
        max_h = target_height - (2 * margin)
        scale_x = max_w / crop_width
        scale_y = max_h / crop_height
        base_scale = min(scale_x, scale_y)
        return base_scale * enlarge_factor, margin

    def create_final_question_pages(self, page_num: int):
        regions, _ = self.detect_questions_with_ocr(page_num)
        if not regions:
            regions = self._create_fallback_regions(page_num)

        output_doc = fitz.open()
        for region in regions:
            new_page = output_doc.new_page(width=792, height=612)
            crop_rect = fitz.Rect(region)
            scale, margin = self.calculate_scaling(crop_rect, enlarge_factor=1.0)
            scaled_w = crop_rect.width * scale
            scaled_h = crop_rect.height * scale
            x_offset = (792 - scaled_w) / 2
            y_offset = (612 - scaled_h) / 2
            target_rect = fitz.Rect(x_offset, y_offset, x_offset + scaled_w, y_offset + scaled_h)
            new_page.show_pdf_page(target_rect, self.doc, page_num, clip=crop_rect)
        return output_doc, len(regions)

    def _create_fallback_regions(self, page_num: int):
        page = self.doc[page_num]
        h, w = page.rect.height, page.rect.width
        regions = []
        for i in range(5):
            y0, y1 = i * h / 5, (i + 1) * h / 5
            regions.append((25, y0, w - 25, y1))
        return regions

    def close(self):
        self.doc.close()


# -------------------------------
# Main App
# -------------------------------
st.title("PDF Question Extractor")
st.markdown("### Extract and enlarge questions from PDF worksheets")

st.markdown("""
<div class="info-box">
    <strong>How it works:</strong><br><br>
    1. Upload your PDF worksheet<br>
    2. Select the page number<br>
    3. Click "Process PDF" to extract questions<br>
    4. Download your enlarged PDF (1x scale, one question per page)
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=['pdf'],
    help="Upload the PDF containing questions you want to extract and enlarge"
)

if uploaded_file is not None:
    st.success(f"File uploaded: {uploaded_file.name}")
    try:
        pdf_bytes = uploaded_file.read()
        temp_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(temp_doc)
        temp_doc.close()

        st.info(f"Total pages in document: {total_pages}")
        page_number = st.number_input(
            "Page Number", min_value=1, max_value=total_pages, value=1, step=1
        )

        st.markdown("---")

        if st.button("Process PDF", type="primary"):
            with st.spinner("Processing PDF..."):
                uploaded_file.seek(0)
                pdf_bytes = uploaded_file.read()
                processor = FinalOCRProcessor(pdf_bytes)
                output_doc, num_questions = processor.create_final_question_pages(page_number - 1)
                output_bytes = output_doc.write()
                output_doc.close()
                processor.close()

                base_name = os.path.splitext(uploaded_file.name)[0]
                output_filename = f"{base_name}_enlarged.pdf"

                st.markdown(f"""
                <div class="success-box">
                    <strong>Processing Complete!</strong><br><br>
                    Detected and extracted <strong>{num_questions}</strong> questions<br>
                    Enlargement: <strong>1x</strong><br>
                    Format: One question per landscape page
                </div>
                """, unsafe_allow_html=True)

                st.download_button(
                    label="Download Processed PDF",
                    data=output_bytes,
                    file_name=output_filename,
                    mime="application/pdf",
                    type="primary"
                )

    except Exception as e:
        st.error(f"Error: {str(e)}")

else:
    st.markdown("""
    <div class="upload-section">
        <h3>Upload a PDF to get started</h3>
        <p>Select a PDF file containing questions you want to extract and enlarge.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #999; font-size: 14px;">
    <p>Created by Derik Vo | N2Y Adaptation Tools</p>
</div>
""", unsafe_allow_html=True)
