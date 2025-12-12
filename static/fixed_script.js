let selectedFiles = [];

// File input handling
document.getElementById('fileInput').addEventListener('change', function(e) {
    console.log('File input changed:', e.target.files);
    handleFileSelect(e.target.files);
});

// Drag and drop handling
const uploadArea = document.getElementById('uploadArea');

uploadArea.addEventListener('dragover', function(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', function(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', function(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    handleFileSelect(e.dataTransfer.files);
});

function handleFileSelect(files) {
    console.log('handleFileSelect called with:', files);
    if (!files || files.length === 0) return;
    
    selectedFiles = [];
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    let validFiles = 0;
    
    for (let file of files) {
        // Validate file type
        if (!allowedTypes.includes(file.type)) {
            showAlert('warning', 'Skipped ' + file.name + ': Invalid file type');
            continue;
        }
        
        // Validate file size (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
            showAlert('warning', 'Skipped ' + file.name + ': File too large (>10MB)');
            continue;
        }
        
        selectedFiles.push(file);
        validFiles++;
    }
    
    if (validFiles === 0) {
        showAlert('danger', 'No valid files selected. Please upload PDF, JPG, or PNG files.');
        return;
    }
    
    // Show file info
    document.getElementById('fileCount').textContent = validFiles + ' file(s) selected';
    
    const fileList = document.getElementById('fileList');
    let fileListHTML = '';
    selectedFiles.forEach(function(file) {
        fileListHTML += '<div class="d-flex justify-content-between align-items-center border-bottom py-1">' +
                       '<span class="text-truncate me-2">' + file.name + '</span>' +
                       '<span class="badge bg-secondary">' + formatFileSize(file.size) + '</span>' +
                       '</div>';
    });
    fileList.innerHTML = fileListHTML;
    
    document.getElementById('fileInfo').style.display = 'block';
    document.getElementById('processBtn').disabled = false;
}

// Form submission
document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    if (!selectedFiles || selectedFiles.length === 0) {
        showAlert('danger', 'Please select files first.');
        return;
    }
    
    processInvoice();
});

function processInvoice() {
    console.log('processInvoice called with files:', selectedFiles);
    const formData = new FormData();
    selectedFiles.forEach(function(file) {
        formData.append('file', file);
    });
    
    // Show progress
    document.querySelector('.progress-container').style.display = 'block';
    document.querySelector('.result-container').style.display = 'none';
    document.getElementById('processBtn').disabled = true;
    
    // Simulate progress
    let progress = 0;
    const progressBar = document.querySelector('.progress-bar');
    const progressText = document.getElementById('progressText');
    
    const progressSteps = [
        { progress: 15, text: 'Uploading ' + selectedFiles.length + ' file(s)...' },
        { progress: 35, text: 'AI processing with LLAMA Maverick...' },
        { progress: 55, text: 'Extracting invoice data...' },
        { progress: 75, text: 'Testing TallyPrime connection...' },
        { progress: 85, text: 'Creating ledgers...' },
        { progress: 95, text: 'Generating vouchers...' }
    ];
    
    let stepIndex = 0;
    const progressInterval = setInterval(function() {
        if (stepIndex < progressSteps.length) {
            const step = progressSteps[stepIndex];
            progressBar.style.width = step.progress + '%';
            progressText.textContent = step.text;
            stepIndex++;
        }
    }, 1000);
    
    // Submit form
    console.log('Submitting to /upload');
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        progressText.textContent = 'Complete!';
        
        setTimeout(function() {
            document.querySelector('.progress-container').style.display = 'none';
            showResults(data);
            document.getElementById('processBtn').disabled = false;
        }, 1000);
    })
    .catch(function(error) {
        clearInterval(progressInterval);
        document.querySelector('.progress-container').style.display = 'none';
        document.getElementById('processBtn').disabled = false;
        showAlert('danger', 'Processing failed: ' + error.message);
    });
}

function showResults(data) {
    const resultContainer = document.querySelector('.result-container');
    const resultHeader = document.getElementById('resultHeader');
    const resultBody = document.getElementById('resultBody');
    
    console.log('Showing results:', data);
    
    // Handle batch processing
    if (data.batch_processing) {
        showBatchResults(data);
        return;
    }
    
    // Single file processing
    if (data.success || data.overall_status === 'partial_success') {
        const headerClass = data.success ? 'bg-success' : 'bg-warning';
        const headerIcon = data.success ? 'fa-check-circle' : 'fa-exclamation-triangle';
        const headerText = data.success ? 'Processing Successful!' : 'Partial Success - Check Details';
        
        resultHeader.className = 'card-header ' + headerClass + ' text-white';
        resultHeader.innerHTML = '<h5 class="mb-0"><i class="fas ' + headerIcon + ' me-2"></i>' + headerText + '</h5>';
        
        let resultHTML = '';
        
        // Show processing steps if available
        if (data.processing_steps) {
            resultHTML += '<div class="mb-4">' +
                '<h6><i class="fas fa-tasks me-2"></i>Processing Steps</h6>' +
                '<div class="row">';
            
            for (let stepName in data.processing_steps) {
                const stepData = data.processing_steps[stepName];
                const statusClass = stepData.status === 'success' ? 'success' : 
                                  stepData.status === 'failed' ? 'danger' : 'warning';
                const statusIcon = stepData.status === 'success' ? 'fa-check-circle' : 
                                 stepData.status === 'failed' ? 'fa-times-circle' : 'fa-clock';
                
                resultHTML += '<div class="col-md-6 mb-2">' +
                    '<div class="card border-' + statusClass + '">' +
                        '<div class="card-body py-2">' +
                            '<div class="d-flex align-items-center">' +
                                '<i class="fas ' + statusIcon + ' text-' + statusClass + ' me-2"></i>' +
                                '<div class="flex-grow-1">' +
                                    '<small class="fw-bold">' + stepName.replace('_', ' ').toUpperCase() + '</small>' +
                                    '<div class="text-muted small">' + stepData.message + '</div>' +
                                '</div>' +
                            '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>';
            }
            resultHTML += '</div></div>';
        }
        
        // Show invoice details if available
        if (data.invoice_data) {
            const invoiceData = data.invoice_data;
            resultHTML += '<div class="row">' +
                '<div class="col-md-6">' +
                    '<h6><i class="fas fa-file-invoice me-2"></i>Invoice Details</h6>' +
                    '<table class="table table-sm">' +
                        '<tr><td><strong>Invoice Number:</strong></td><td>' + (invoiceData.invoice_number || 'N/A') + '</td></tr>' +
                        '<tr><td><strong>Vendor:</strong></td><td>' + (invoiceData.vendor_name || 'N/A') + '</td></tr>' +
                        '<tr><td><strong>Date:</strong></td><td>' + (invoiceData.date || 'N/A') + '</td></tr>' +
                        '<tr><td><strong>Total Amount:</strong></td><td class="text-success fw-bold">' + formatCurrency(invoiceData.total_amount || 0) + '</td></tr>' +
                        '<tr><td><strong>Tax Amount:</strong></td><td>' + formatCurrency(invoiceData.tax_amount || 0) + '</td></tr>' +
                    '</table>' +
                '</div>' +
                '<div class="col-md-6">' +
                    '<h6><i class="fas fa-cogs me-2"></i>Processing Info</h6>' +
                    '<table class="table table-sm">' +
                        '<tr><td><strong>Pages Processed:</strong></td><td>' + (data.pages_processed || 1) + '</td></tr>' +
                        '<tr><td><strong>Line Items:</strong></td><td>' + (invoiceData.line_items ? invoiceData.line_items.length : 0) + '</td></tr>' +
                        '<tr><td><strong>TallyPrime Status:</strong></td><td><span class="badge ' + (data.tally_status === 'SUCCESS' ? 'bg-success' : 'bg-warning') + '">' + (data.tally_status || 'UNKNOWN') + '</span></td></tr>' +
                    '</table>' +
                '</div>' +
            '</div>';
        }
        
        // Show download links if available
        if (data.json_file || data.xml_file) {
            resultHTML += '<div class="text-center mt-4">' +
                '<div class="btn-group" role="group">';
            
            if (data.json_file) {
                const jsonFileName = data.json_file.split('/').pop();
                resultHTML += '<a href="/download/' + jsonFileName + '" class="btn btn-outline-primary">' +
                    '<i class="fas fa-download me-2"></i>Download JSON</a>';
            }
            
            if (data.xml_file) {
                const xmlFileName = data.xml_file.split('/').pop();
                resultHTML += '<a href="/download/' + xmlFileName + '" class="btn btn-outline-success">' +
                    '<i class="fas fa-download me-2"></i>Download XML</a>';
            }
            
            resultHTML += '<button class="btn btn-primary" onclick="location.reload()">' +
                '<i class="fas fa-plus me-2"></i>Process Another</button>' +
            '</div></div>';
        }
        
        resultBody.innerHTML = resultHTML;
        
    } else {
        // Complete failure
        resultHeader.className = 'card-header bg-danger text-white';
        resultHeader.innerHTML = '<h5 class="mb-0"><i class="fas fa-exclamation-triangle me-2"></i>Processing Failed</h5>';
        
        let errorHTML = '<div class="alert alert-danger">' +
            '<h6><i class="fas fa-bug me-2"></i>Error Details</h6>';
        
        if (data.error) {
            errorHTML += '<p class="mb-2"><strong>Error:</strong> ' + data.error + '</p>';
        }
        
        if (data.processing_steps) {
            errorHTML += '<p class="mb-2"><strong>Processing Steps:</strong></p><ul>';
            for (let stepName in data.processing_steps) {
                const stepData = data.processing_steps[stepName];
                const statusIcon = stepData.status === 'success' ? '✅' : 
                                 stepData.status === 'failed' ? '❌' : '⏳';
                errorHTML += '<li>' + statusIcon + ' ' + stepName.replace('_', ' ').toUpperCase() + ': ' + stepData.message + '</li>';
            }
            errorHTML += '</ul>';
        }
        
        errorHTML += '</div>' +
            '<div class="text-center">' +
                '<button class="btn btn-primary" onclick="location.reload()">' +
                    '<i class="fas fa-redo me-2"></i>Try Again' +
                '</button>' +
            '</div>';
        
        resultBody.innerHTML = errorHTML;
    }
    
    resultContainer.style.display = 'block';
    resultContainer.scrollIntoView({ behavior: 'smooth' });
}

function showBatchResults(data) {
    const resultContainer = document.querySelector('.result-container');
    const resultHeader = document.getElementById('resultHeader');
    const resultBody = document.getElementById('resultBody');
    
    const successRate = (data.successful_files / data.total_files * 100).toFixed(1);
    const headerClass = data.successful_files === data.total_files ? 'bg-success' : 
                       data.successful_files > 0 ? 'bg-warning' : 'bg-danger';
    
    resultHeader.className = 'card-header ' + headerClass + ' text-white';
    resultHeader.innerHTML = '<h5 class="mb-0"><i class="fas fa-files me-2"></i>Batch Processing Complete</h5>';
    
    let resultHTML = '<div class="row mb-4">' +
        '<div class="col-md-3"><div class="text-center"><h3 class="text-primary">' + data.total_files + '</h3><small class="text-muted">Total Files</small></div></div>' +
        '<div class="col-md-3"><div class="text-center"><h3 class="text-success">' + data.successful_files + '</h3><small class="text-muted">Successful</small></div></div>' +
        '<div class="col-md-3"><div class="text-center"><h3 class="text-danger">' + data.failed_files + '</h3><small class="text-muted">Failed</small></div></div>' +
        '<div class="col-md-3"><div class="text-center"><h3 class="text-info">' + successRate + '%</h3><small class="text-muted">Success Rate</small></div></div>' +
    '</div>';
    
    // Show individual results
    resultHTML += '<div class="accordion" id="resultsAccordion">';
    
    for (let i = 0; i < data.results.length; i++) {
        const result = data.results[i];
        const statusClass = result.success ? 'success' : 'danger';
        const statusIcon = result.success ? 'fa-check-circle' : 'fa-times-circle';
        
        resultHTML += '<div class="accordion-item">' +
            '<h2 class="accordion-header" id="heading' + i + '">' +
                '<button class="accordion-button ' + (i === 0 ? '' : 'collapsed') + '" type="button" data-bs-toggle="collapse" data-bs-target="#collapse' + i + '">' +
                    '<i class="fas ' + statusIcon + ' text-' + statusClass + ' me-2"></i>' +
                    '<strong>' + result.original_filename + '</strong>' +
                    (result.success ? 
                        '<span class="badge bg-success ms-2">' + formatCurrency(result.invoice_data?.total_amount || 0) + '</span>' :
                        '<span class="badge bg-danger ms-2">Failed</span>'
                    ) +
                '</button>' +
            '</h2>' +
            '<div id="collapse' + i + '" class="accordion-collapse collapse ' + (i === 0 ? 'show' : '') + '" data-bs-parent="#resultsAccordion">' +
                '<div class="accordion-body">';
        
        if (result.success) {
            // Show successful result details
            if (result.processing_steps) {
                resultHTML += '<div class="row mb-3">';
                for (let stepName in result.processing_steps) {
                    const stepData = result.processing_steps[stepName];
                    const stepStatusClass = stepData.status === 'success' ? 'success' : 
                                           stepData.status === 'failed' ? 'danger' : 'warning';
                    const stepStatusIcon = stepData.status === 'success' ? 'fa-check' : 
                                          stepData.status === 'failed' ? 'fa-times' : 'fa-clock';
                    
                    resultHTML += '<div class="col-md-6 mb-2">' +
                        '<div class="d-flex align-items-center">' +
                            '<i class="fas ' + stepStatusIcon + ' text-' + stepStatusClass + ' me-2"></i>' +
                            '<div>' +
                                '<small class="fw-bold">' + stepName.replace('_', ' ').toUpperCase() + '</small>' +
                                '<div class="text-muted small">' + stepData.message + '</div>' +
                            '</div>' +
                        '</div>' +
                    '</div>';
                }
                resultHTML += '</div>';
            }
            
            if (result.invoice_data) {
                resultHTML += '<div class="row">' +
                    '<div class="col-md-6">' +
                        '<h6>Invoice Details</h6>' +
                        '<table class="table table-sm">' +
                            '<tr><td><strong>Invoice #:</strong></td><td>' + (result.invoice_data.invoice_number || 'N/A') + '</td></tr>' +
                            '<tr><td><strong>Vendor:</strong></td><td>' + (result.invoice_data.vendor_name || 'N/A') + '</td></tr>' +
                            '<tr><td><strong>Amount:</strong></td><td class="text-success fw-bold">' + formatCurrency(result.invoice_data.total_amount || 0) + '</td></tr>' +
                        '</table>' +
                    '</div>' +
                    '<div class="col-md-6">' +
                        '<h6>Processing Info</h6>' +
                        '<table class="table table-sm">' +
                            '<tr><td><strong>Pages:</strong></td><td>' + (result.pages_processed || 1) + '</td></tr>' +
                            '<tr><td><strong>Items:</strong></td><td>' + (result.invoice_data.line_items?.length || 0) + '</td></tr>' +
                            '<tr><td><strong>Tally Status:</strong></td><td><span class="badge bg-' + (result.success ? 'success' : 'warning') + '">' + (result.tally_status || 'UNKNOWN') + '</span></td></tr>' +
                        '</table>' +
                    '</div>' +
                '</div>';
            }
        } else {
            // Show error details
            resultHTML += '<div class="alert alert-danger">' +
                '<h6><i class="fas fa-exclamation-triangle me-2"></i>Processing Failed</h6>' +
                '<p class="mb-0">' + (result.error || 'Unknown error occurred') + '</p>';
            
            if (result.processing_steps) {
                resultHTML += '<p class="mt-2 mb-0"><strong>Steps:</strong></p><ul class="mb-0">';
                for (let stepName in result.processing_steps) {
                    const stepData = result.processing_steps[stepName];
                    const statusIcon = stepData.status === 'success' ? '✅' : 
                                     stepData.status === 'failed' ? '❌' : '⏳';
                    resultHTML += '<li>' + statusIcon + ' ' + stepName.replace('_', ' ').toUpperCase() + ': ' + stepData.message + '</li>';
                }
                resultHTML += '</ul>';
            }
            
            resultHTML += '</div>';
        }
        
        resultHTML += '</div></div></div>';
    }
    
    resultHTML += '</div>' +
        '<div class="text-center mt-4">' +
            '<button class="btn btn-primary" onclick="location.reload()">' +
                '<i class="fas fa-plus me-2"></i>Process More Files' +
            '</button>' +
        '</div>';
    
    resultBody.innerHTML = resultHTML;
    resultContainer.style.display = 'block';
    resultContainer.scrollIntoView({ behavior: 'smooth' });
}