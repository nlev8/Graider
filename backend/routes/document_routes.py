"""
Document handling API routes for Graider.
Handles file browsing, document parsing, and folder operations.
"""
import os
import subprocess
import base64
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file

document_bp = Blueprint('document', __name__)


@document_bp.route('/api/browse')
def browse_for_path():
    """Open a file/folder picker dialog (macOS)."""
    browse_type = request.args.get('type', 'folder')

    try:
        if browse_type == 'folder':
            script = '''
            tell application "System Events"
                activate
                set folderPath to POSIX path of (choose folder with prompt "Select Folder")
                return folderPath
            end tell
            '''
        else:
            script = '''
            tell application "System Events"
                activate
                set filePath to POSIX path of (choose file with prompt "Select File")
                return filePath
            end tell
            '''

        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip()
            return jsonify({"path": path})
        else:
            return jsonify({"path": None, "error": "Cancelled or no selection"})

    except subprocess.TimeoutExpired:
        return jsonify({"path": None, "error": "Timeout"})
    except Exception as e:
        return jsonify({"path": None, "error": str(e)})


@document_bp.route('/api/open-folder', methods=['POST'])
def open_folder():
    """Open a folder in Finder."""
    data = request.json
    folder = data.get('folder', '')

    if os.path.exists(folder):
        os.system(f'open "{folder}"')
        return jsonify({"status": "opened"})
    return jsonify({"error": "Folder not found"})


@document_bp.route('/api/serve-file', methods=['GET'])
def serve_file_endpoint():
    """Serve a local file for inline preview (images, etc.)."""
    filepath = request.args.get('path', '')
    if not filepath or not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_file(filepath)


@document_bp.route('/api/parse-document', methods=['POST'])
def parse_document():
    """Parse an uploaded Word/PDF document and convert to HTML."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"})

    file = request.files['file']
    filename = file.filename.lower()
    file_data = file.read()

    try:
        if filename.endswith('.docx'):
            return _parse_docx(file_data, file.filename)
        elif filename.endswith('.pdf'):
            return _parse_pdf(file_data, file.filename)
        elif filename.endswith('.txt'):
            return _parse_txt(file_data, file.filename)
        else:
            return jsonify({"error": "Unsupported file type. Use .docx, .pdf, or .txt"})

    except Exception as e:
        import traceback
        return jsonify({"error": f"{str(e)}\n{traceback.format_exc()}"})


def _parse_docx(file_data, filename):
    """Parse Word document to HTML."""
    import io

    # Try mammoth first for best HTML conversion
    try:
        import mammoth
        from docx import Document

        result = mammoth.convert_to_html(io.BytesIO(file_data))
        html = result.value

        styled_html = f'''
        <style>
            body {{ font-family: Georgia, serif; line-height: 1.6; }}
            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
            td, th {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
            th {{ background: #f5f5f5; font-weight: bold; }}
            p {{ margin: 10px 0; }}
            h1, h2, h3 {{ margin: 20px 0 10px 0; }}
            ul, ol {{ margin: 10px 0; padding-left: 25px; }}
        </style>
        {html}
        '''

        # Extract plain text for marking
        doc = Document(io.BytesIO(file_data))
        plain_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                plain_text.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    plain_text.append(row_text)

        # Try to extract full document title from metadata or first heading
        doc_title = None
        try:
            # Check document properties for title
            if doc.core_properties.title:
                doc_title = doc.core_properties.title
        except:
            pass

        # If no metadata title, use first heading or first paragraph
        if not doc_title and plain_text:
            # First non-empty line is likely the title
            doc_title = plain_text[0].strip()

        return jsonify({
            "html": styled_html,
            "text": '\n'.join(plain_text),
            "filename": filename,
            "doc_title": doc_title,  # Full title from document content
            "type": "html"
        })

    except ImportError:
        # Fallback to python-docx only
        from docx import Document
        from docx.oxml.table import CT_Tbl
        from docx.oxml.text.paragraph import CT_P
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(io.BytesIO(file_data))
        html_parts = ['<div style="font-family: Georgia, serif; line-height: 1.6;">']

        for child in doc.element.body.iterchildren():
            if isinstance(child, CT_P):
                para = Paragraph(child, doc)
                if para.text.strip():
                    style = para.style.name if para.style else ''
                    if 'Heading 1' in style:
                        html_parts.append(f'<h1>{para.text}</h1>')
                    elif 'Heading 2' in style:
                        html_parts.append(f'<h2>{para.text}</h2>')
                    elif 'Heading' in style:
                        html_parts.append(f'<h3>{para.text}</h3>')
                    else:
                        html_parts.append(f'<p>{para.text}</p>')
            elif isinstance(child, CT_Tbl):
                table = Table(child, doc)
                html_parts.append('<table style="border-collapse: collapse; width: 100%; margin: 15px 0;">')
                for row_idx, row in enumerate(table.rows):
                    html_parts.append('<tr>')
                    for cell in row.cells:
                        tag = 'th' if row_idx == 0 else 'td'
                        style = 'border: 1px solid #ccc; padding: 8px 12px; background: #f5f5f5;' if row_idx == 0 else 'border: 1px solid #ccc; padding: 8px 12px;'
                        html_parts.append(f'<{tag} style="{style}">{cell.text}</{tag}>')
                    html_parts.append('</tr>')
                html_parts.append('</table>')

        html_parts.append('</div>')

        plain_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                plain_text.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    plain_text.append(row_text)

        return jsonify({
            "html": ''.join(html_parts),
            "text": '\n'.join(plain_text),
            "filename": filename,
            "type": "html"
        })


def _parse_pdf(file_data, filename):
    """Parse PDF document to HTML with images."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_data, filetype="pdf")
        images_html = []
        plain_text = []

        for page_num, page in enumerate(doc):
            mat = fitz.Matrix(1.5, 1.5)  # 150 DPI
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            img_base64 = base64.b64encode(img_data).decode('utf-8')

            images_html.append(f'''
                <div style="margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="background: #6366f1; color: white; padding: 5px 15px; font-size: 12px;">Page {page_num + 1}</div>
                    <img src="data:image/png;base64,{img_base64}" style="width: 100%; display: block;" />
                </div>
            ''')
            plain_text.append(page.get_text())

        doc.close()

        full_html = f'''
        <div style="background: #e5e5e5; padding: 20px;">
            {''.join(images_html)}
        </div>
        '''

        return jsonify({
            "html": full_html,
            "text": '\n\n'.join(plain_text),
            "filename": filename,
            "type": "html"
        })

    except ImportError:
        return jsonify({"error": "PDF support requires PyMuPDF. Run: pip3 install pymupdf"})


def _parse_txt(file_data, filename):
    """Parse text file."""
    text = file_data.decode('utf-8', errors='ignore')
    html = f'<pre style="font-family: Monaco, monospace; white-space: pre-wrap; line-height: 1.6;">{text}</pre>'
    return jsonify({
        "html": html,
        "text": text,
        "filename": filename,
        "type": "html"
    })
