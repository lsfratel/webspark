"""
File Upload Example
This example demonstrates how to handle file uploads in WebSpark:
- Handling multipart form data
- Saving uploaded files
- Returning file information
"""

import os
import uuid

from webspark.core import View, WebSpark, path
from webspark.http import JsonResponse, Request
from webspark.utils import HTTPException

# Directory to store uploaded files
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class FileUploadView(View):
    """Handle file uploads."""

    def handle_post(self, request: Request):
        """Handle file upload."""
        # Check if request has files
        if not request.files:
            raise HTTPException("No files uploaded", status_code=400)

        uploaded_files = []

        # Process each uploaded file
        for field_name, file_list in request.files.items():
            if isinstance(file_list, list):
                for file_info in file_list:
                    # Generate a unique filename
                    filename = f"{uuid.uuid4()}_{field_name}"
                    file_path = os.path.join(UPLOAD_DIR, filename)

                    # Save the file
                    with open(file_path, "wb") as f:
                        f.write(file_info["file"].read())

                    # Store file information
                    uploaded_files.append(
                        {
                            "field_name": field_name,
                            "original_name": file_info["filename"],
                            "saved_name": filename,
                            "content_type": file_info["content_type"],
                        }
                    )
            else:
                # Generate a unique filename
                filename = f"{uuid.uuid4()}_{field_name}"
                file_path = os.path.join(UPLOAD_DIR, filename)

                # Save the file
                with open(file_path, "wb") as f:
                    f.write(file_list["file"].read())

                # Store file information
                uploaded_files.append(
                    {
                        "field_name": field_name,
                        "original_name": file_list["filename"],
                        "saved_name": filename,
                        "content_type": file_list["content_type"],
                    }
                )

        return JsonResponse(
            {
                "message": f"Successfully uploaded {len(uploaded_files)} file(s)",
                "files": uploaded_files,
            },
            status=201,
        )


class FileListView(View):
    """List uploaded files."""

    def handle_get(self, request):
        """Return list of uploaded files."""
        files = []
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                if os.path.isfile(file_path):
                    stat = os.stat(file_path)
                    files.append(
                        {
                            "name": filename,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                        }
                    )

        return JsonResponse({"files": files})


# Create the app
app = WebSpark(debug=True)

# Add routes
app.add_paths(
    [
        path("/upload", view=FileUploadView.as_view()),
        path("/files", view=FileListView.as_view()),
    ]
)

if __name__ == "__main__":
    # For development purposes, you can run this with a WSGI server like:
    # gunicorn examples.file_upload_example:app
    print("File Upload Example")
    print("Run with: gunicorn examples.file_upload_example:app")
