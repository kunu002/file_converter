import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from pdf2docx import Converter
import pythoncom
from docx2pdf import convert
import threading

# Initialize COM
pythoncom.CoInitialize()

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'pdf', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def jpg_to_pdf(input_path, output_path):
    try:
        image = Image.open(input_path)
        pdf_path = output_path if output_path.endswith('.pdf') else output_path + '.pdf'
        image.save(pdf_path, "PDF", resolution=100.0)
        return pdf_path
    except Exception as e:
        raise Exception(f"Error converting {input_path} to PDF: {str(e)}")

def pdf_to_word(input_path, output_path):
    try:
        cv = Converter(input_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()
        return output_path
    except Exception as e:
        raise Exception(f"Error converting {input_path} to Word: {str(e)}")

def word_to_pdf(input_path, output_path):
    def convert_thread():
        pythoncom.CoInitialize()
        try:
            convert(input_path, output_path)
        except Exception as e:
            raise Exception(f"Error converting {input_path} to PDF: {str(e)}")
        finally:
            pythoncom.CoUninitialize()

    thread = threading.Thread(target=convert_thread)
    thread.start()
    thread.join()
    return output_path

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
            input_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}"))
            file.save(input_path)
            
            conversion_type = request.form['conversion']
            output_filename = f"{unique_id}_converted_{filename.split('.')[0]}"
            
            try:
                if conversion_type == 'jpg_to_pdf':
                    output_path = jpg_to_pdf(input_path, os.path.abspath(os.path.join(app.config['OUTPUT_FOLDER'], f"{output_filename}.pdf")))
                elif conversion_type == 'pdf_to_word':
                    output_path = pdf_to_word(input_path, os.path.abspath(os.path.join(app.config['OUTPUT_FOLDER'], f"{output_filename}.docx")))
                elif conversion_type == 'word_to_pdf':
                    output_path = word_to_pdf(input_path, os.path.abspath(os.path.join(app.config['OUTPUT_FOLDER'], f"{output_filename}.pdf")))
                else:
                    return jsonify({'error': 'Invalid conversion type'}), 400
                
                return send_file(output_path, as_attachment=True)
            except Exception as e:
                return jsonify({'error': str(e)}), 500
            finally:
                # Remove input file
                if os.path.exists(input_path):
                    os.remove(input_path)
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    
    return render_template('upload.html')

def cleanup_old_files():
    current_time = datetime.now()
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
            if current_time - file_modified > timedelta(minutes=30):
                try:
                    os.remove(file_path)
                except:
                    pass  

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(debug=True)
    cleanup_old_files()
    pythoncom.CoUninitialize()  # Uninitialize COM when the application exits