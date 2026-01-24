import os


def cleanup_temp_files(file_paths):
    """
    Delete temporary files.
    
    Args:
        file_paths (list): List of file paths to delete
    """
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting temporary file {file_path}: {str(e)}")


def create_temp_file(suffix=''):
    """
    Create a temporary file and return its path.
    
    Args:
        suffix (str): Suffix for the temporary file (e.g., '.pdf', '.docx')
        
    Returns:
        str: Path to the created temporary file
    """
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    return temp_file.name