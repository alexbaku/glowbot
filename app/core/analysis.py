from PIL import Image
from io import BytesIO
import logging
from typing import Optional, Tuple
from app.services.claude import ClaudeService

logger = logging.getLogger(__name__)

class ImageAnalyzer:
    def __init__(self):
        self.claude_service = ClaudeService()
        self.valid_formats = {'JPEG', 'PNG'}
        self.max_size = (1024, 1024)  # Maximum image dimensions

    async def process_image(self, image_data: bytes) -> Tuple[bytes, dict]:
        """Process and validate image before analysis"""
        try:
            # Open image using PIL
            image = Image.open(BytesIO(image_data))

            # Validate format
            if image.format not in self.valid_formats:
                raise ValueError(f"Invalid image format. Supported formats: {self.valid_formats}")

            # Resize if necessary while maintaining aspect ratio
            if image.size[0] > self.max_size[0] or image.size[1] > self.max_size[1]:
                image.thumbnail(self.max_size, Image.Resampling.LANCZOS)

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Save processed image to bytes
            output = BytesIO()
            image.save(output, format='JPEG', quality=85)
            processed_image = output.getvalue()

            return processed_image

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise

    async def analyze_skin(self, 
        image_data: bytes, 
        user_id: Optional[str] = None
    ) -> dict:
        """Analyze skin condition from image"""
        try:
            # Process image
            processed_image = await self.process_image(image_data)

            # Get analysis from Claude
            analysis = await self.claude_service.analyze_image(processed_image)

            # Extract key information
            skin_conditions = self._extract_skin_conditions(analysis['analysis'])

            return {
                "analysis": analysis['analysis'],
                "skin_conditions": skin_conditions,
                "user_id": user_id,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Error in skin analysis: {str(e)}")
            raise

    def _extract_skin_conditions(self, analysis: str) -> dict:
        """Extract structured information from analysis text"""
        conditions = {
            "skin_type": None,
            "concerns": [],
            "recommendations": []
        }

        # Add logic to parse the analysis text and extract key information
        # This is a placeholder - you would implement more sophisticated parsing
        # based on the actual structure of Claude's responses

        return conditions