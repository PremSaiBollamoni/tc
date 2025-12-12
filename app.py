#!/usr/bin/env python3
"""
Invoice Processing Web Application
Professional UI for TallyPrime integration
"""

from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
import os
import json
from werkzeug.utils import secure_filename
from pathlib import Path
import logging
from datetime import datetime
import traceback

# Import our processing modules
try:
    from config import validate_config, get_config
    from invoice_processor import InvoiceProcessor
    from complete_working_solution import CompleteTallyIntegration
except ImportError as e:
    print(f"Import error: {e}")
    # Create dummy functions for testing
    def validate_config():
        return {'deepinfra_token': os.environ.get('DEEPINFRA_TOKEN', ''), 'tally_host': 'localhost', 'tally_port': '9000'}
    def get_config():
        return validate_config()

app = Flask(__name__)
app.secret_key = 'invoice_processing_secret_key_2024'

# Configuration
UPLOAD_FOLDER = '/tmp/uploads'
RESULTS_FOLDER = '/tmp/results'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# Create directories in /tmp (writable in serverless)
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
except:
    pass  # Ignore errors in serverless environment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_invoice_api(file_path):
    """Process invoice and return detailed results"""
    processing_steps = {
        'ai_processing': {'status': 'pending', 'message': '', 'data': None},
        'tally_connection': {'status': 'pending', 'message': '', 'data': None},
        'ledger_creation': {'status': 'pending', 'message': '', 'data': None},
        'voucher_creation': {'status': 'pending', 'message': '', 'data': None}
    }
    
    try:
        config = validate_config()
        
        # Step 1: AI Processing
        processing_steps['ai_processing']['status'] = 'processing'
        try:
            processor = InvoiceProcessor(config['deepinfra_token'])
            json_results = processor.process_invoice_file(file_path)
            merged_json = processor.merge_json_data(json_results)
            
            processing_steps['ai_processing']['status'] = 'success'
            processing_steps['ai_processing']['message'] = f'Extracted data from {len(json_results)} page(s)'
            processing_steps['ai_processing']['data'] = {
                'pages': len(json_results),
                'invoice_number': merged_json.get('invoice_number'),
                'vendor_name': merged_json.get('vendor_name'),
                'total_amount': merged_json.get('total_amount')
            }
        except Exception as e:
            processing_steps['ai_processing']['status'] = 'failed'
            processing_steps['ai_processing']['message'] = f'AI processing failed: {str(e)}'
            raise
        
        # Step 2: TallyPrime Connection Test
        processing_steps['tally_connection']['status'] = 'processing'
        try:
            import requests
            base_url = f"http://{config['tally_host']}:{config['tally_port']}"
            response = requests.get(base_url, timeout=5)
            
            if response.status_code == 200:
                processing_steps['tally_connection']['status'] = 'success'
                processing_steps['tally_connection']['message'] = f'Connected to TallyPrime on {config["tally_host"]}:{config["tally_port"]}'
            else:
                processing_steps['tally_connection']['status'] = 'failed'
                processing_steps['tally_connection']['message'] = f'TallyPrime not responding (HTTP {response.status_code})'
        except Exception as e:
            processing_steps['tally_connection']['status'] = 'failed'
            processing_steps['tally_connection']['message'] = f'Cannot connect to TallyPrime: {str(e)}'
        
        # Step 3: TallyPrime Integration
        processing_steps['ledger_creation']['status'] = 'processing'
        processing_steps['voucher_creation']['status'] = 'processing'
        
        tally = CompleteTallyIntegration()
        result = tally.import_complete_invoice(merged_json)
        
        # Update ledger creation status
        processing_steps['ledger_creation']['status'] = 'success'
        processing_steps['ledger_creation']['message'] = 'Ledgers created successfully'
        processing_steps['ledger_creation']['data'] = {
            'vendor_ledger': merged_json.get('vendor_name'),
            'item_ledgers': [item.get('description') for item in merged_json.get('line_items', [])]
        }
        
        # Update voucher creation status
        if result['success']:
            processing_steps['voucher_creation']['status'] = 'success'
            processing_steps['voucher_creation']['message'] = 'Voucher created successfully in TallyPrime'
        else:
            processing_steps['voucher_creation']['status'] = 'failed'
            processing_steps['voucher_creation']['message'] = f'Voucher creation failed: {result.get("error", "Unknown error")}'
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = os.path.join(RESULTS_FOLDER, f"invoice_{timestamp}.json")
        xml_file = os.path.join(RESULTS_FOLDER, f"voucher_{timestamp}.xml")
        
        # Save JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(merged_json, f, indent=2, ensure_ascii=False)
        
        # Save XML if available
        if result.get('xml_file') and os.path.exists(result['xml_file']):
            import shutil
            shutil.copy(result['xml_file'], xml_file)
        
        return {
            'success': result['success'],
            'invoice_data': merged_json,
            'pages_processed': len(json_results),
            'json_file': json_file,
            'xml_file': xml_file if os.path.exists(xml_file) else None,
            'error': result.get('error'),
            'tally_status': 'SUCCESS' if result['success'] else 'FAILED',
            'processing_steps': processing_steps,
            'overall_status': 'success' if result['success'] else 'partial_success'
        }
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        
        # Mark remaining steps as failed
        for step_name, step_data in processing_steps.items():
            if step_data['status'] == 'pending':
                step_data['status'] = 'failed'
                step_data['message'] = 'Skipped due to previous error'
        
        return {
            'success': False,
            'error': str(e),
            'processing_steps': processing_steps,
            'overall_status': 'failed',
            'traceback': traceback.format_exc()
        }

@app.route('/')
def index():
    """Main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f"<h1>Invoice Processing App</h1><p>Status: Running</p><p>Error: {str(e)}</p>"

@app.route('/debug')
def debug():
    """Debug endpoint"""
    return jsonify({'status': 'App is running', 'timestamp': datetime.now().isoformat()})

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    try:
        logger.info("Upload request received")
        logger.info(f"Request files: {request.files}")
        logger.info(f"Request form: {request.form}")
        # Handle multiple files
        files = request.files.getlist('file')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'success': False, 'error': 'No files selected'})
        
        results = []
        total_success = 0
        total_files = len(files)
        
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                
                # Process the invoice
                result = process_invoice_api(file_path)
                
                # Add file info to result
                result['uploaded_file'] = filename
                result['original_filename'] = file.filename
                result['file_size'] = os.path.getsize(file_path)
                
                if result['success']:
                    total_success += 1
                
                results.append(result)
            else:
                results.append({
                    'success': False,
                    'error': f'Invalid file type: {file.filename}',
                    'original_filename': file.filename
                })
        
        return jsonify({
            'success': total_success > 0,
            'batch_processing': True,
            'total_files': total_files,
            'successful_files': total_success,
            'failed_files': total_files - total_success,
            'results': results
        })
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/test-connection')
def test_connection():
    """Test TallyPrime connection"""
    try:
        import requests
        config = get_config()
        base_url = f"http://{config['tally_host']}:{config['tally_port']}"
        
        response = requests.get(base_url, timeout=5)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'status': 'Connected',
                'host': config['tally_host'],
                'port': config['tally_port']
            })
        else:
            return jsonify({
                'success': False,
                'status': 'Not responding',
                'error': f'HTTP {response.status_code}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'Connection failed',
            'error': str(e)
        })

@app.route('/download/<path:filename>')
def download_file(filename):
    """Download generated files"""
    try:
        file_path = os.path.join(RESULTS_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history')
def history():
    """Show processing history"""
    try:
        results = []
        results_dir = Path(RESULTS_FOLDER)
        
        for json_file in results_dir.glob("invoice_*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Get file info
                stat = json_file.stat()
                
                results.append({
                    'timestamp': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    'invoice_number': data.get('invoice_number', 'N/A'),
                    'vendor_name': data.get('vendor_name', 'N/A'),
                    'total_amount': data.get('total_amount', 0),
                    'json_file': json_file.name,
                    'xml_file': json_file.name.replace('invoice_', 'voucher_').replace('.json', '.xml')
                })
            except:
                continue
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return render_template('history.html', results=results)
        
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        return render_template('history.html', results=[], error=str(e))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)