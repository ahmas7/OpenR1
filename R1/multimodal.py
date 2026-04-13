"""
R1 - Multimodal Input Handler
Image upload, file processing, vision capabilities
"""
import base64
import io
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class UploadedFile:
    name: str
    content: bytes
    content_type: str
    size: int


class ImageProcessor:
    def __init__(self):
        self.temp_dir = Path("E:/MYAI/R1/data/uploads")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_image(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Process uploaded image"""
        try:
            from PIL import Image
            import pytesseract
            
            image = Image.open(io.BytesIO(file_data))
            
            result = {
                "filename": filename,
                "size": len(file_data),
                "format": image.format,
                "mode": image.mode,
                "dimensions": image.size,
            }
            
            ocr_text = pytesseract.image_to_string(image)
            if ocr_text.strip():
                result["ocr_text"] = ocr_text.strip()[:1000]
            
            return {"success": True, "data": result}
        except ImportError:
            return await self.basic_process(file_data, filename)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def basic_process(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Basic image processing without OCR"""
        try:
            from PIL import Image
            image = Image.open(io.BytesIO(file_data))
            
            return {
                "success": True,
                "data": {
                    "filename": filename,
                    "size": len(file_data),
                    "format": image.format,
                    "dimensions": image.size
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def analyze_with_vision(self, image_data: bytes, prompt: str = "Describe this image") -> Dict[str, Any]:
        """Analyze image with vision model"""
        return {"success": False, "error": "Vision API not configured"}


class FileProcessor:
    SUPPORTED = {
        "txt": "text",
        "md": "text",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "csv": "csv",
        "xml": "xml",
        "html": "html",
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "h": "c",
        "css": "css",
        "sql": "sql",
        "sh": "bash",
        "bat": "batch",
        "ps1": "powershell",
    }
    
    def __init__(self):
        self.temp_dir = Path("E:/MYAI/R1/data/uploads")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_file(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Process uploaded file"""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        file_type = self.SUPPORTED.get(ext, "binary")
        
        result = {
            "filename": filename,
            "size": len(file_data),
            "type": file_type,
            "extension": ext
        }
        
        try:
            if file_type == "text" or file_type in ["python", "javascript", "json", "yaml", "sql", "bash"]:
                content = file_data.decode("utf-8")
                result["content"] = content[:50000]
                result["line_count"] = len(content.splitlines())
                
            elif file_type == "json":
                content = file_data.decode("utf-8")
                data = json.loads(content)
                result["content"] = json.dumps(data, indent=2)[:50000]
                
            elif file_type == "csv":
                import csv
                content = file_data.decode("utf-8")
                lines = content.splitlines()
                reader = csv.reader(lines)
                rows = list(reader)[:100]
                result["rows"] = rows[:100]
                result["columns"] = rows[0] if rows else []
                result["row_count"] = len(lines)
                
            elif ext in ["png", "jpg", "jpeg", "gif", "bmp", "webp"]:
                return await ImageProcessor().process_image(file_data, filename)
            
            else:
                result["content"] = f"Binary file ({len(file_data)} bytes)"
            
            return {"success": True, "data": result}
            
        except UnicodeDecodeError:
            return {"success": True, "data": {**result, "content": "Binary file"}}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def save_upload(self, file_data: bytes, filename: str) -> str:
        """Save uploaded file"""
        path = self.temp_dir / filename
        path.write_bytes(file_data)
        return str(path)


class MultimodalHandler:
    def __init__(self):
        self.image_processor = ImageProcessor()
        self.file_processor = FileProcessor()
    
    async def handle_upload(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """Handle any file upload"""
        return await self.file_processor.process_file(file_data, filename)
    
    async def extract_text(self, file_data: bytes, filename: str) -> str:
        """Extract text from file"""
        result = await self.file_processor.process_file(file_data, filename)
        
        if result.get("success"):
            data = result.get("data", {})
            if "ocr_text" in data:
                return data["ocr_text"]
            if "content" in data:
                return data["content"]
        
        return ""


multimodal = MultimodalHandler()
