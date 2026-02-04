import os
import tempfile
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch


def convert_word_to_pdf(word_path):
    """
    Convert a Word document (.docx) to PDF format.
    
    Args:
        word_path (str): Path to the input Word document
        
    Returns:
        str: Path to the output PDF file, or None if conversion fails
    """
    try:
        # Load the Word document
        doc = Document(word_path)
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_output:
            output_path = temp_output.name
        
        # Create PDF using ReportLab
        pdf_doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Extract text from Word document and add to PDF
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():  # Only add non-empty paragraphs
                p = Paragraph(paragraph.text, styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.2 * inch))  # Add some spacing
        
        # Build the PDF
        pdf_doc.build(story)
        
        return output_path
    
    except Exception as e:
        print(f"Error converting Word to PDF: {str(e)}")
        # Clean up in case of error
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
        return None