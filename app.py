import os
import uuid
import logging
import io
from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from pdf2docx import Converter as PDFToWordConverter
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import tempfile

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Use temporary directory for file operations
UPLOAD_FOLDER = tempfile.gettempdir()
OUTPUT_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB limit

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def jpg_to_pdf(input_path, output_path):
    try:
        image = Image.open(input_path)
        pdf_path = output_path if output_path.endswith('.pdf') else output_path + '.pdf'
        image.save(pdf_path, "PDF", resolution=100.0)
        return pdf_path
    except Exception as e:
        app.logger.error(f"Error converting {input_path} to PDF: {str(e)}")
        raise

def pdf_to_word(input_path, output_path):
    try:
        cv = PDFToWordConverter(input_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()
        return output_path
    except Exception as e:
        app.logger.error(f"Error converting {input_path} to Word: {str(e)}")
        raise

def word_to_pdf(input_path, output_path):
    try:
        # Read the Word document
        doc = Document(input_path)
        
        # Create a PDF
        pdf_buffer = io.BytesIO()
        pdf = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        
        # Create story (content) for the PDF
        styles = getSampleStyleSheet()
        story = []
        
        for para in doc.paragraphs:
            p = Paragraph(para.text, styles['Normal'])
            story.append(p)
        
        # Build the PDF
        pdf.build(story)
        
        # Save the PDF
        with open(output_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        return output_path
    except Exception as e:
        app.logger.error(f"Error converting {input_path} to PDF: {str(e)}")
        raise

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
            file.save(input_path)
            
            conversion_type = request.form['conversion']
            output_filename = f"{unique_id}_converted_{filename.split('.')[0]}"
            
            try:
                if conversion_type == 'jpg_to_pdf':
                    output_path = jpg_to_pdf(input_path, os.path.join(app.config['OUTPUT_FOLDER'], f"{output_filename}.pdf"))
                elif conversion_type == 'pdf_to_word':
                    output_path = pdf_to_word(input_path, os.path.join(app.config['OUTPUT_FOLDER'], f"{output_filename}.docx"))
                elif conversion_type == 'word_to_pdf':
                    output_path = word_to_pdf(input_path, os.path.join(app.config['OUTPUT_FOLDER'], f"{output_filename}.pdf"))
                else:
                    return jsonify({'error': 'Invalid conversion type'}), 400
                
                return send_file(output_path, as_attachment=True)
            except Exception as e:
                app.logger.error(f"Conversion error: {str(e)}")
                return jsonify({'error': 'An error occurred during conversion'}), 500
            finally:
                # Clean up input file
                if os.path.exists(input_path):
                    os.remove(input_path)
                # Clean up output file after sending
                if 'output_path' in locals() and os.path.exists(output_path):
                    os.remove(output_path)
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    
    return render_template('upload.html')

@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f"An internal error occurred: {str(error)}")
    return jsonify(error="An internal server error occurred"), 500

if __name__ == '__main__':
    app.run(debug=True)
