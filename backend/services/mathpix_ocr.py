"""
Mathpix OCR Service for Graider.

Converts handwritten math images to LaTeX/text using the Mathpix API.
Used in the grading pipeline when students upload photos of their work.

Pricing: ~$0.002 per image.
Docs: https://mathpix.com/docs/convert/api-reference
"""
import os
import re
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
_app_dir = Path(__file__).parent.parent.parent
load_dotenv(_app_dir / '.env', override=True)


def _get_credentials():
    """Get Mathpix API credentials from environment."""
    app_id = os.getenv('MATHPIX_APP_ID', '')
    app_key = os.getenv('MATHPIX_APP_KEY', '')
    if not app_id or not app_key:
        return None, None
    return app_id, app_key


def is_available():
    """Check if Mathpix API credentials are configured."""
    app_id, app_key = _get_credentials()
    return bool(app_id and app_key)


def image_to_latex(image_data, formats=None):
    """
    Convert an image (base64 data URI or raw base64) to LaTeX/text.

    Args:
        image_data: Base64-encoded image string, with or without data URI prefix
                    (e.g., "data:image/png;base64,iVBOR..." or raw base64)
        formats: List of desired output formats. Default: ["latex_styled", "text"]
                 Options: "text", "latex_styled", "latex_normal", "asciimath",
                          "mathml", "latex_list"

    Returns:
        dict with keys:
            - 'latex': LaTeX string of the recognized math (latex_styled)
            - 'text': Plain text representation
            - 'confidence': Recognition confidence (0-1)
            - 'raw': Full Mathpix API response
            - 'error': Error message if failed, None if success
    """
    app_id, app_key = _get_credentials()
    if not app_id or not app_key:
        return {
            'latex': '',
            'text': '',
            'confidence': 0,
            'raw': {},
            'error': 'Mathpix API credentials not configured. Set MATHPIX_APP_ID and MATHPIX_APP_KEY in .env'
        }

    # Handle data URI prefix
    if image_data.startswith('data:'):
        # Already a proper data URI — use as src directly
        src = image_data
    else:
        # Raw base64 — assume PNG
        src = f"data:image/png;base64,{image_data}"

    if formats is None:
        formats = ["latex_styled", "text"]

    headers = {
        "app_id": app_id,
        "app_key": app_key,
        "Content-Type": "application/json",
    }

    payload = {
        "src": src,
        "formats": formats,
        "data_options": {
            "include_asciimath": True,
            "include_latex": True,
        },
        "include_line_data": False,
    }

    try:
        response = requests.post(
            "https://api.mathpix.com/v3/text",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()

        latex = result.get('latex_styled', result.get('latex_normal', ''))
        text = result.get('text', '')
        confidence = _extract_confidence(result)

        return {
            'latex': latex,
            'text': text,
            'confidence': confidence,
            'raw': result,
            'error': result.get('error', None),
        }

    except requests.exceptions.Timeout:
        return {
            'latex': '',
            'text': '',
            'confidence': 0,
            'raw': {},
            'error': 'Mathpix API request timed out',
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else 'unknown'
        body = e.response.text[:200] if e.response else ''
        return {
            'latex': '',
            'text': '',
            'confidence': 0,
            'raw': {},
            'error': f'Mathpix API HTTP {status}: {body}',
        }
    except Exception as e:
        return {
            'latex': '',
            'text': '',
            'confidence': 0,
            'raw': {},
            'error': f'Mathpix API error: {str(e)}',
        }


def _extract_confidence(result):
    """Extract overall confidence score from Mathpix response."""
    # Mathpix returns confidence_rate at top level for single expressions
    if 'confidence_rate' in result:
        return result['confidence_rate']
    # For multi-line, average line confidences
    if 'line_data' in result:
        lines = result['line_data']
        if lines:
            confs = [l.get('confidence', 0) for l in lines if 'confidence' in l]
            return sum(confs) / len(confs) if confs else 0
    # Fallback: check confidence field
    return result.get('confidence', 0)


def extract_answer_from_image(image_data, question_text='', question_type='math_equation'):
    """
    High-level function: extract a student's answer from an uploaded image.

    Sends the image to Mathpix for OCR, then returns a structured result
    suitable for the grading pipeline.

    Args:
        image_data: Base64-encoded image (with or without data URI prefix)
        question_text: The question being answered (for context)
        question_type: Type of question (math_equation, short_answer, etc.)

    Returns:
        dict with:
            - 'extracted_text': The recognized text/math as a string
            - 'latex': LaTeX representation (for math)
            - 'confidence': OCR confidence (0-1)
            - 'ocr_source': 'mathpix'
            - 'error': Error message if any
    """
    result = image_to_latex(image_data)

    if result['error']:
        return {
            'extracted_text': '',
            'latex': '',
            'confidence': 0,
            'ocr_source': 'mathpix',
            'error': result['error'],
        }

    # For math questions, prefer LaTeX; for text questions, prefer plain text
    if question_type in ('math_equation', 'geometry', 'data_table'):
        extracted = result['latex'] or result['text']
    else:
        extracted = result['text'] or result['latex']

    # Clean up common Mathpix artifacts
    extracted = _clean_ocr_text(extracted)

    return {
        'extracted_text': extracted,
        'latex': result['latex'],
        'confidence': result['confidence'],
        'ocr_source': 'mathpix',
        'error': None,
    }


def _clean_ocr_text(text):
    """Clean common OCR artifacts from Mathpix output."""
    if not text:
        return ''
    # Remove surrounding whitespace
    text = text.strip()
    # Remove Mathpix's surrounding dollar signs for inline math
    if text.startswith('$') and text.endswith('$'):
        text = text[1:-1].strip()
    # Remove double dollar signs for display math
    if text.startswith('$$') and text.endswith('$$'):
        text = text[2:-2].strip()
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text
