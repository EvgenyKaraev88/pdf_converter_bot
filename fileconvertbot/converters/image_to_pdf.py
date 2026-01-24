import os
import tempfile
from PIL import Image
import img2pdf


def convert_image_to_pdf(image_path):
    """
    Convert an image file to PDF format.
    
    Args:
        image_path (str): Path to the input image file
        
    Returns:
        str: Path to the output PDF file, or None if conversion fails
    """
    try:
        # Open and verify the image
        with Image.open(image_path) as img:
            # Convert image to RGB if necessary (some formats cause issues with img2pdf)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
        
        # Create a temporary PDF file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_output:
            output_path = temp_output.name
        
        # Convert image to PDF using img2pdf
        with open(output_path, "wb") as pdf_file:
            with open(image_path, "rb") as image_file:
                pdf_file.write(img2pdf.convert(image_file))
        
        return output_path
    
    except Exception as e:
        print(f"Error converting image to PDF: {str(e)}")
        # Clean up in case of error
        if 'output_path' in locals() and os.path.exists(output_path):
            os.remove(output_path)
        return None