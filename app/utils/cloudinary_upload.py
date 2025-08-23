import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv
import tempfile
import shutil
from fastapi import UploadFile

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

async def upload_profile_photo(file):
    """
    Upload a profile photo to Cloudinary
    
    Args:
        file: The file object from FastAPI's UploadFile
        
    Returns:
        str: The secure URL of the uploaded image
    """
    # Create a temporary file to handle the upload
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # If file is a FastAPI UploadFile object
        if isinstance(file, UploadFile):
            # Read the content of the file
            content = await file.read()
            # Write the content to the temporary file
            temp_file.write(content)
            # Reset the file position so it can be read again if needed
            await file.seek(0)
        else:
            # If it's already a file-like object
            shutil.copyfileobj(file, temp_file)
        
        temp_file_path = temp_file.name
    
    try:
        # Upload from the temporary file
        result = cloudinary.uploader.upload(temp_file_path, folder="profile_photos")
        return result.get("secure_url")
    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)