import os


def validate_file_type(file_path, expected_extensions):
    """
    Validate if the file has an expected extension.
    
    Args:
        file_path (str): Path to the file
        expected_extensions (list): List of expected extensions (e.g., ['.jpg', '.png'])
        
    Returns:
        bool: True if file extension is valid, False otherwise
    """
    _, ext = os.path.splitext(file_path)
    return ext.lower() in [ext.lower() for ext in expected_extensions]


def validate_file_size(file_path, max_size_mb=20):
    """
    Validate if the file size is within the allowed limit.
    
    Args:
        file_path (str): Path to the file
        max_size_mb (int): Maximum allowed size in MB
        
    Returns:
        bool: True if file size is within limit, False otherwise
    """
    size_bytes = os.path.getsize(file_path)
    size_mb = size_bytes / (1024 * 1024)  # Convert bytes to MB
    return size_mb <= max_size_mb