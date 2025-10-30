import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageEnhance
from pathlib import Path
import io

st.set_page_config(
    page_title="PDF Question Extractor",
    page_icon="📄",
    layout="wide"
)

# Custom CSS to match your website theme
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-size: 16px;
        border: none;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0056b3;
        transform: translateY(-2px);
    }
    .upload-section {
        border: 2px dashed #ddd;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
    }
    .info-box {
        background-color: #f8f9fa;
        border-left: 4px solid #007bff;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

class FinalOCRProcessor:
    def __init__(self, input_pdf):
        self.doc = fitz.open(stream=input_pdf, filetype="pdf")

    def extract_text_with_ocr(self, page_num: int):
        """Extract text from PDF page using OCR"""
        page = self.doc[page_num]
        pix = page.get_pixmap(dpi=200)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        return ocr_data, img.size, page.rect

    def detect_questions_with_ocr(self, page_num: int):
        """Use OCR to detect question regions accurately"""
        ocr_data, img_size, page_rect = self.extract_text_with_ocr(page_num)
        page = self.doc[page_num]
        scale_x = page_rect.width / img_size[0]
        scale_y = page_rect.height / img_size[1]

        questions = []
        for i, text in enumerate(ocr_data['text']):
            text = text.strip()
            if text and text[0].isdigit() and any(marker in text for marker in ['.', ')']):
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

        questions.sort(key=lambda q: q['y'])

        if questions:
            min_question_x = min(q['x'] for q in questions)
            left_margin = max(5, min_question_x - 25)
        else:
            left_margin = 30

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
        target_width = 792
        target_height = 612
        margin = 20
        max_content_width = target_width - (2 * margin)
        max_content_height = target_height - (2 * margin)
        scale_x = max_content_width / crop_width
        scale_y = max_content_height / crop_height
        base_scale = min(scale_x, scale_y)
        final_scale = base_scale * enlarge_factor
        return final_scale, margin

    def create_final_question_pages(self, page_num: int, enlarge_factor=1.25):
        """Create question pages with user-controlled enlargement"""
        regions, questions = self.detect_questions_with_ocr(page_num)

        if not regions:
            regions = self._create_fallback_regions(page_num)

        output_doc = fitz.open()

        for i, region in enumerate(regions, 1):
            new_page = output_doc.new_page(width=792, height=612)
            crop_rect = fitz.Rect(region)
            scale, margin = self.calculate_scaling(crop_rect, enlarge_factor)
            scaled_width = crop_rect.width * scale
            scaled_height = crop_rect.height * scale
            x_offset = (792 - scaled_width) / 2
            y_offset = (612 - scaled_height) / 2
            target_rect = fitz.Rect(
                x_offset,
                y_offset,
                x_offset + scaled_width,
                y_offset + scaled_height
            )
            new_page.show_pdf_page(target_rect, self.doc, page_num, clip=crop_rect)

        return output_doc, len(regions)

    def _create_fallback_regions(self, page_num: int):
        """Simple fallback regions"""
        page = self.doc[page_num]
        page_height = page.rect.height
        page_width = page.rect.width
        num_regions = 5
        region_height = page_height / num_regions
        regions = []
        for i in range(num_regions):
            y_start = i * region_height
            y_end = (i + 1) * region_height
            regions.append((25, y_start, page_width - 25, y_end))
        return regions

    def close(self):
        self.doc.close()

# Main App
st.title("📄 PDF Question Extractor & Enlarger")
st.markdown("### N2Y Adaptation Tool")
st.markdown("Extract individual questions from PDF worksheets and enlarge them for better accessibility.")

# Info box
st.markdown("""
<div class="info-box">
    <strong>ℹ️ How it works:</strong>
    <ol>
        <li>Upload your PDF file containing questions</li>
        <li>Select the page number you want to process</li>
        <li>Adjust the enlargement factor (1x = original size, 8x = 8 times larger)</li>
        <li>Click "Process PDF" to extract and enlarge each question</li>
        <li>Download your adapted PDF with one question per page</li>
    </ol>
</div>
""", unsafe_allow_html=True)

# File upload
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload the PDF containing questions you want to extract and enlarge"
    )

if uploaded_file is not None:
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    
    pdf_bytes = uploaded_file.read()
    temp_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(temp_doc)
    temp_doc.close()
    
    st.info(f"📖 Total pages in document: {total_pages}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        page_number = st.number_input(
            "Page Number",
            min_value=1,
            max_value=total_pages,
            value=min(1, total_pages),
            help="Select which page to process (1-indexed)"
        )
    
    with col2:
        enlarge_factor = st.slider(
            "Enlargement Factor",
            min_value=1.0,
            max_value=10.0,
            value=8.0,
            step=0.5,
            help="How much to enlarge the questions (1x = original size)"
        )
    
    if st.button("🚀 Process PDF", type="primary"):
        with st.spinner("Processing PDF... This may take a moment."):
            try:
                uploaded_file.seek(0)
                pdf_bytes = uploaded_file.read()
                
                processor = FinalOCRProcessor(pdf_bytes)
                output_doc, num_questions = processor.create_final_question_pages(
                    page_number - 1,
                    enlarge_factor=enlarge_factor
                )
                
                output_bytes = output_doc.write()
                output_doc.close()
                processor.close()
                
                st.markdown(f"""
                <div class="success-box">
                    <strong>🎉 Processing Complete!</strong><br>
                    Detected and extracted <strong>{num_questions}</strong> questions<br>
                    Enlargement factor: <strong>{enlarge_factor}x</strong><br>
                    Output format: One question per landscape page
                </div>
                """, unsafe_allow_html=True)
                
                output_filename = f"enlarged_questions_{enlarge_factor}x.pdf"
                st.download_button(
                    label="⬇️ Download Processed PDF",
                    data=output_bytes,
                    file_name=output_filename,
                    mime="application/pdf",
                    type="primary"
                )
                
            except Exception as e:
                st.error(f"❌ Error processing PDF: {str(e)}")
                st.error("Please check that the PDF contains clearly numbered questions.")

else:
    st.markdown("""
    <div class="upload-section">
        <h3>👆 Upload a PDF to get started</h3>
        <p>Select a PDF file containing questions you want to extract and enlarge.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 14px;">
    <p>Created by Derik Vo | Part of the N2Y Adaptation Tools Suite</p>
    <p>For support or questions, please contact your administrator.</p>
</div>
""", unsafe_allow_html=True)