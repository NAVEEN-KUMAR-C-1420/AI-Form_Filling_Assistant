/**
 * AI Form Filling Assistant - Popup Script
 * Handles popup UI interactions and communication with background service
 */

// DOM Elements
const elements = {
  // Sections
  authSection: document.getElementById('auth-section'),
  mainSection: document.getElementById('main-section'),
  uploadSection: document.getElementById('upload-section'),
  previewSection: document.getElementById('preview-section'),
  manageDataSection: document.getElementById('manage-data-section'),
  digilockerImportSection: document.getElementById('digilocker-import-section'),
  
  // Auth
  loginForm: document.getElementById('login-form'),
  signupForm: document.getElementById('signup-form'),
  loginError: document.getElementById('login-error'),
  signupError: document.getElementById('signup-error'),
  
  // User info
  userName: document.getElementById('user-name'),
  userEmail: document.getElementById('user-email'),
  userInitials: document.getElementById('user-initials'),
  logoutBtn: document.getElementById('logout-btn'),
  
  // Status
  statusMessage: document.getElementById('status-message'),
  websiteStatus: document.getElementById('website-status'),
  
  // Profile
  profileDataList: document.getElementById('profile-data-list'),
  manageDataLink: document.getElementById('manage-data-link'),
  manageDataList: document.getElementById('manage-data-list'),
  deleteAllDataBtn: document.getElementById('delete-all-data-btn'),
  
  // Actions
  detectFormsBtn: document.getElementById('detect-forms-btn'),
  uploadDocBtn: document.getElementById('upload-doc-btn'),
  
  // Upload
  uploadForm: document.getElementById('upload-form'),
  uploadArea: document.getElementById('upload-area'),
  fileInput: document.getElementById('file-input'),
  filePreview: document.getElementById('file-preview'),
  fileName: document.getElementById('file-name'),
  removeFile: document.getElementById('remove-file'),
  uploadBtn: document.getElementById('upload-btn'),
  uploadProgress: document.getElementById('upload-progress'),
  
  // Preview
  previewForm: document.getElementById('preview-form'),
  extractedFields: document.getElementById('extracted-fields'),
  docTypeBadge: document.getElementById('doc-type-badge'),
  confidenceBadge: document.getElementById('confidence-badge'),
  
  // DigiLocker
  digilockerStatus: document.getElementById('digilocker-status'),
  digilockerConnectBtn: document.getElementById('digilocker-connect-btn'),
  digilockerImportBtn: document.getElementById('digilocker-import-btn'),
  digilockerDocsList: document.getElementById('digilocker-docs-list'),
  importSelectedBtn: document.getElementById('import-selected-btn'),
  backFromDigilocker: document.getElementById('back-from-digilocker')
};

// State
let currentState = {
  isAuthenticated: false,
  user: null,
  currentTab: null,
  extractedData: null,
  documentId: null,
  digilockerConnected: false,
  digilockerDocs: [],
  selectedDigilockerDocs: []
};

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  await checkAuthState();
  await getCurrentTab();
  setupEventListeners();
});

// Check authentication state
async function checkAuthState() {
  try {
    const response = await sendMessage({ type: 'GET_AUTH_STATE' });
    
    if (response.success && response.data.isAuthenticated) {
      currentState.isAuthenticated = true;
      currentState.user = response.data.user;
      showMainSection();
      await loadProfileData();
    } else {
      showAuthSection();
    }
  } catch (error) {
    console.error('Auth check error:', error);
    showAuthSection();
  }
}

// Get current tab info
async function getCurrentTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentState.currentTab = tab;
    checkWebsiteStatus(tab.url);
  } catch (error) {
    console.error('Tab query error:', error);
  }
}

// Check if current website is supported
async function checkWebsiteStatus(url) {
  const response = await sendMessage({ type: 'CHECK_WEBSITE', payload: { url } });
  
  if (response.success) {
    const { supported, reason } = response.data;
    const statusIcon = elements.websiteStatus.querySelector('.status-icon');
    
    if (supported) {
      elements.statusMessage.textContent = 'Ready to autofill';
      elements.websiteStatus.classList.add('supported');
      elements.websiteStatus.classList.remove('unsupported');
      statusIcon.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="#4CAF50"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>`;
    } else {
      elements.statusMessage.textContent = reason;
      elements.websiteStatus.classList.add('unsupported');
      elements.websiteStatus.classList.remove('supported');
      statusIcon.innerHTML = `<svg width="24" height="24" viewBox="0 0 24 24" fill="#ff9800"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>`;
    }
  }
}

// Load user's profile data
async function loadProfileData() {
  const response = await sendMessage({ type: 'GET_PROFILE_DATA' });
  
  if (response.success && response.data.entities) {
    const entities = response.data.entities;
    let html = '';
    
    // Updated field order to include regional name and driving license fields
    const fieldOrder = ['full_name', 'full_name_regional', 'date_of_birth', 'gender', 'aadhaar_number', 'pan_number', 'driving_license_number', 'voter_id_number', 'father_name', 'blood_group', 'address'];
    
    for (const field of fieldOrder) {
      if (entities[field]) {
        html += `
          <div class="data-item">
            <span class="data-label">${formatFieldName(field)}</span>
            <span class="data-value">${entities[field].value}</span>
          </div>
        `;
      }
    }
    
    if (html) {
      elements.profileDataList.innerHTML = html;
    } else {
      elements.profileDataList.innerHTML = '<p class="no-data">No data saved yet. Upload a document to get started.</p>';
    }
  } else {
    elements.profileDataList.innerHTML = '<p class="no-data">No data saved yet. Upload a document to get started.</p>';
  }
  
  // Also check DigiLocker status
  checkDigiLockerStatus();
}

// Setup event listeners
function setupEventListeners() {
  // Auth tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const tab = e.target.dataset.tab;
      switchAuthTab(tab);
    });
  });
  
  // Login form
  elements.loginForm.addEventListener('submit', handleLogin);
  
  // Signup form
  elements.signupForm.addEventListener('submit', handleSignup);
  
  // Logout
  elements.logoutBtn.addEventListener('click', handleLogout);
  
  // Detect forms
  elements.detectFormsBtn.addEventListener('click', detectForms);
  
  // Upload document
  elements.uploadDocBtn.addEventListener('click', () => showSection('upload'));
  
  // Manage data link
  if (elements.manageDataLink) {
    elements.manageDataLink.addEventListener('click', (e) => {
      e.preventDefault();
      showSection('manage');
      loadManageData();
    });
  }
  
  // Delete all data button
  if (elements.deleteAllDataBtn) {
    elements.deleteAllDataBtn.addEventListener('click', handleDeleteAllData);
  }
  
  // Back buttons
  document.getElementById('back-from-upload').addEventListener('click', () => showSection('main'));
  document.getElementById('back-from-preview').addEventListener('click', () => showSection('upload'));
  document.getElementById('back-from-manage')?.addEventListener('click', () => showSection('main'));
  
  // File upload
  elements.uploadArea.addEventListener('click', () => elements.fileInput.click());
  elements.uploadArea.addEventListener('dragover', handleDragOver);
  elements.uploadArea.addEventListener('drop', handleDrop);
  elements.fileInput.addEventListener('change', handleFileSelect);
  elements.removeFile.addEventListener('click', removeSelectedFile);
  
  // Upload form
  elements.uploadForm.addEventListener('submit', handleUpload);
  
  // Preview form
  elements.previewForm.addEventListener('submit', handleConfirmData);
  document.getElementById('cancel-extraction').addEventListener('click', () => showSection('main'));
  
  // DigiLocker events
  if (elements.digilockerConnectBtn) {
    elements.digilockerConnectBtn.addEventListener('click', handleDigiLockerConnect);
  }
  if (elements.digilockerImportBtn) {
    elements.digilockerImportBtn.addEventListener('click', () => {
      showSection('digilocker-import');
      loadDigiLockerDocuments();
    });
  }
  if (elements.backFromDigilocker) {
    elements.backFromDigilocker.addEventListener('click', () => showSection('main'));
  }
  if (elements.importSelectedBtn) {
    elements.importSelectedBtn.addEventListener('click', handleImportSelectedDocuments);
  }
}

// Switch auth tabs
function switchAuthTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  
  elements.loginForm.classList.toggle('hidden', tab !== 'login');
  elements.signupForm.classList.toggle('hidden', tab !== 'signup');
}

// Handle login
async function handleLogin(e) {
  e.preventDefault();
  
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  
  elements.loginError.classList.add('hidden');
  
  const response = await sendMessage({
    type: 'LOGIN',
    payload: { email, password }
  });
  
  if (response.success) {
    currentState.isAuthenticated = true;
    currentState.user = response.data.user;
    showMainSection();
    await loadProfileData();
  } else {
    elements.loginError.textContent = response.error;
    elements.loginError.classList.remove('hidden');
  }
}

// Handle signup
async function handleSignup(e) {
  e.preventDefault();
  
  const name = document.getElementById('signup-name').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const phone = document.getElementById('signup-phone').value.trim();
  const password = document.getElementById('signup-password').value;
  const confirmPassword = document.getElementById('signup-confirm-password').value;
  
  elements.signupError.classList.add('hidden');
  
  // Validate passwords match
  if (password !== confirmPassword) {
    elements.signupError.textContent = 'Passwords do not match.';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  // Validate password strength
  if (password.length < 8) {
    elements.signupError.textContent = 'Password must be at least 8 characters.';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  if (!/[A-Z]/.test(password)) {
    elements.signupError.textContent = 'Password must contain at least one uppercase letter.';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  if (!/[a-z]/.test(password)) {
    elements.signupError.textContent = 'Password must contain at least one lowercase letter.';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  if (!/\d/.test(password)) {
    elements.signupError.textContent = 'Password must contain at least one digit.';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    elements.signupError.textContent = 'Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  // Validate name
  if (!name) {
    elements.signupError.textContent = 'Full name is required.';
    elements.signupError.classList.remove('hidden');
    return;
  }
  
  // Show loading state
  const submitBtn = elements.signupForm.querySelector('button[type="submit"]');
  const originalText = submitBtn.textContent;
  submitBtn.textContent = 'Creating Account...';
  submitBtn.disabled = true;
  
  try {
    const response = await sendMessage({
      type: 'SIGNUP',
      payload: {
        email,
        password,
        full_name: name,
        phone_number: phone || null
      }
    });
    
    if (response.success) {
      // Clear form fields
      document.getElementById('signup-name').value = '';
      document.getElementById('signup-email').value = '';
      document.getElementById('signup-phone').value = '';
      document.getElementById('signup-password').value = '';
      document.getElementById('signup-confirm-password').value = '';
      
      if (response.data.autoLogin) {
        // Auto-logged in after signup
        currentState.isAuthenticated = true;
        currentState.user = response.data.user;
        showMainSection();
        await loadProfileData();
        showNotification('Account created successfully!', 'success');
      } else {
        // Registration succeeded but need to login manually
        showNotification('Account created! Please login.', 'success');
        switchAuthTab('login');
        document.getElementById('login-email').value = email;
      }
    } else {
      elements.signupError.textContent = response.error;
      elements.signupError.classList.remove('hidden');
    }
  } catch (error) {
    elements.signupError.textContent = 'An error occurred. Please try again.';
    elements.signupError.classList.remove('hidden');
  } finally {
    submitBtn.textContent = originalText;
    submitBtn.disabled = false;
  }
}

// Handle logout
async function handleLogout() {
  await sendMessage({ type: 'LOGOUT' });
  currentState.isAuthenticated = false;
  currentState.user = null;
  showAuthSection();
}

// Detect forms on current page
async function detectForms() {
  if (!currentState.currentTab) return;
  
  try {
    const response = await chrome.tabs.sendMessage(currentState.currentTab.id, {
      type: 'DETECT_FORMS'
    });
    
    if (response.success) {
      showNotification(`Found ${response.data.fields.length} fillable fields`);
    }
  } catch (error) {
    showNotification('Could not detect forms on this page', 'error');
  }
}

// File handling
function handleDragOver(e) {
  e.preventDefault();
  elements.uploadArea.classList.add('dragover');
}

function handleDrop(e) {
  e.preventDefault();
  elements.uploadArea.classList.remove('dragover');
  
  const file = e.dataTransfer.files[0];
  if (file) {
    handleFile(file);
  }
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) {
    handleFile(file);
  }
}

function handleFile(file) {
  // Validate file
  const validTypes = ['image/jpeg', 'image/png', 'image/tiff', 'application/pdf'];
  const maxSize = 10 * 1024 * 1024; // 10MB
  
  if (!validTypes.includes(file.type)) {
    showNotification('Invalid file type. Please upload JPG, PNG, TIFF, or PDF.', 'error');
    return;
  }
  
  if (file.size > maxSize) {
    showNotification('File too large. Maximum size is 10MB.', 'error');
    return;
  }
  
  // Show file preview
  elements.fileName.textContent = file.name;
  elements.filePreview.classList.remove('hidden');
  elements.uploadArea.classList.add('hidden');
  elements.uploadBtn.disabled = false;
  
  // Store file for upload
  currentState.selectedFile = file;
}

function removeSelectedFile() {
  currentState.selectedFile = null;
  elements.fileInput.value = '';
  elements.filePreview.classList.add('hidden');
  elements.uploadArea.classList.remove('hidden');
  elements.uploadBtn.disabled = true;
}

// Handle document upload
async function handleUpload(e) {
  e.preventDefault();
  
  const docType = document.getElementById('doc-type').value;
  const file = currentState.selectedFile;
  
  if (!docType || !file) {
    showNotification('Please select document type and file', 'error');
    return;
  }
  
  // Show progress
  elements.uploadProgress.classList.remove('hidden');
  elements.uploadBtn.disabled = true;
  
  try {
    // Step 1: Upload the document
    const uploadFormData = new FormData();
    uploadFormData.append('document_type', docType);
    uploadFormData.append('file', file);
    
    // Use loopback host for reliability on Windows
    const uploadResponse = await fetch('http://127.0.0.1:8000/documents/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${await getAuthToken()}`
      },
      body: uploadFormData
    });
    
    if (!uploadResponse.ok) {
      const errorData = await uploadResponse.json();
      throw new Error(errorData.detail || 'Upload failed');
    }
    
    const uploadData = await uploadResponse.json();
    console.log('Upload response:', uploadData);
    
    // Update progress bar
    const progressBar = elements.uploadProgress.querySelector('.progress-bar');
    progressBar.style.width = '50%';
    
    // Step 2: Extract data from the document
    const extractFormData = new FormData();
    extractFormData.append('document_id', uploadData.document_id);
    
    const extractResponse = await fetch('http://127.0.0.1:8000/documents/extract', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${await getAuthToken()}`
      },
      body: extractFormData
    });
    
    progressBar.style.width = '100%';
    
    if (!extractResponse.ok) {
      const errorData = await extractResponse.json();
      throw new Error(errorData.detail || 'Extraction failed');
    }
    
    const extractData = await extractResponse.json();
    console.log('Extract response:', extractData);
    
    // Show preview section with real extracted data
    showExtractionPreview(extractData);
    
  } catch (error) {
    console.error('Upload/extract error:', error);
    // Provide clearer guidance for common failure modes
    if (!(await getAuthToken())) {
      showNotification('Upload failed: Please login first.', 'error');
    } else if (error.message && error.message.includes('fetch')) {
      showNotification('Upload failed: Could not reach server. Ensure the app is running on 127.0.0.1:8000.', 'error');
    } else {
      showNotification('Upload failed: ' + (error.message || 'Unknown error'), 'error');
    }
  } finally {
    elements.uploadProgress.classList.add('hidden');
    elements.uploadBtn.disabled = false;
  }
}

// Get auth token from storage
async function getAuthToken() {
  const data = await chrome.storage.local.get(['authState']);
  return data.authState?.accessToken;
}

// Show extraction preview
function showExtractionPreview(data) {
  currentState.extractedData = data;
  currentState.documentId = data.document_id;
  
  // Update badges
  elements.docTypeBadge.textContent = formatFieldName(data.document_type);
  
  // Fix confidence calculation - ensure it's between 0-100%
  let confidence = data.overall_confidence;
  // If confidence is already a percentage (> 1), don't multiply by 100
  if (confidence > 1) {
    confidence = Math.min(100, confidence); // Cap at 100%
  } else {
    confidence = confidence * 100; // Convert 0-1 to percentage
  }
  elements.confidenceBadge.textContent = `${Math.round(confidence)}% Confidence`;
  
  // Build fields HTML
  let html = '';
  data.entities.forEach(entity => {
    // Normalize confidence score (handle both 0-1 and percentage formats)
    let entityConfidence = entity.confidence_score;
    if (entityConfidence > 1) {
      entityConfidence = entityConfidence / 100; // Convert percentage to 0-1
    }
    const lowConfidence = entityConfidence < 0.8;
    html += `
      <div class="field-row ${lowConfidence ? 'low-confidence' : ''}">
        <label>${formatFieldName(entity.entity_type)}</label>
        <div class="field-input-group">
          <input type="text" 
                 data-entity-id="${entity.id}" 
                 value="${entity.value}"
                 class="field-input">
          <label class="checkbox-label">
            <input type="checkbox" 
                   data-approve="${entity.id}" 
                   checked>
            Approve
          </label>
        </div>
        ${lowConfidence ? '<span class="warning-text">⚠️ Low confidence - please verify</span>' : ''}
      </div>
    `;
  });
  
  elements.extractedFields.innerHTML = html;
  showSection('preview');
}

// Handle data confirmation
async function handleConfirmData(e) {
  e.preventDefault();
  
  const consent = document.getElementById('storage-consent').checked;
  if (!consent) {
    showNotification('Please provide consent to continue', 'error');
    return;
  }
  
  // Collect entity updates
  const entities = [];
  document.querySelectorAll('[data-entity-id]').forEach(input => {
    const id = input.dataset.entityId;
    const approveCheckbox = document.querySelector(`[data-approve="${id}"]`);
    
    entities.push({
      entity_id: id,
      new_value: input.value,
      is_approved: approveCheckbox.checked
    });
  });
  
  try {
    // Send confirmation to API
    const formData = new FormData();
    formData.append('document_id', currentState.documentId);
    formData.append('entities', JSON.stringify(entities));
    formData.append('consent_given', 'true');
    formData.append('consent_text', 'User confirmed extracted data for storage');
    
    const response = await fetch('http://127.0.0.1:8000/documents/confirm', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${await getAuthToken()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        document_id: currentState.documentId,
        entities: entities,
        consent_given: true,
        consent_text: 'User confirmed extracted data for storage'
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to save data');
    }
    
    showNotification('Data saved successfully!', 'success');
    
    // Clear upload state and reset the upload form
    clearUploadState();
    
    showSection('main');
    await loadProfileData();
  } catch (error) {
    console.error('Confirm error:', error);
    showNotification('Failed to save: ' + error.message, 'error');
  }
}

// Clear upload state after successful submission
function clearUploadState() {
  currentState.selectedFile = null;
  currentState.documentId = null;
  currentState.extractedData = null;
  
  if (elements.fileInput) {
    elements.fileInput.value = '';
  }
  if (elements.filePreview) {
    elements.filePreview.classList.add('hidden');
  }
  if (elements.uploadArea) {
    elements.uploadArea.classList.remove('hidden');
  }
  if (elements.uploadBtn) {
    elements.uploadBtn.disabled = true;
  }
  
  // Reset doc type selection
  const docTypeSelect = document.getElementById('doc-type');
  if (docTypeSelect) {
    docTypeSelect.value = '';
  }
}

// Show/hide sections
function showSection(section) {
  elements.authSection.classList.add('hidden');
  elements.mainSection.classList.add('hidden');
  elements.uploadSection.classList.add('hidden');
  elements.previewSection.classList.add('hidden');
  if (elements.manageDataSection) {
    elements.manageDataSection.classList.add('hidden');
  }
  if (elements.digilockerImportSection) {
    elements.digilockerImportSection.classList.add('hidden');
  }
  
  switch (section) {
    case 'auth':
      elements.authSection.classList.remove('hidden');
      break;
    case 'main':
      elements.mainSection.classList.remove('hidden');
      break;
    case 'upload':
      elements.uploadSection.classList.remove('hidden');
      break;
    case 'preview':
      elements.previewSection.classList.remove('hidden');
      break;
    case 'manage':
      if (elements.manageDataSection) {
        elements.manageDataSection.classList.remove('hidden');
      }
      break;
    case 'digilocker-import':
      if (elements.digilockerImportSection) {
        elements.digilockerImportSection.classList.remove('hidden');
      }
      break;
  }
}

function showAuthSection() {
  showSection('auth');
}

function showMainSection() {
  if (currentState.user) {
    elements.userName.textContent = currentState.user.full_name || currentState.user.email;
    elements.userEmail.textContent = currentState.user.email;
    elements.userInitials.textContent = getInitials(currentState.user.full_name || currentState.user.email);
  }
  showSection('main');
}

// Utility functions
function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, resolve);
  });
}

function formatFieldName(fieldType) {
  // Custom labels for specific field types
  const customLabels = {
    'full_name': 'Full Name',
    'full_name_regional': 'Name (Regional)',
    'date_of_birth': 'Date of Birth',
    'aadhaar_number': 'Aadhaar Number',
    'pan_number': 'PAN Number',
    'voter_id_number': 'EPIC Number',
    'father_name': "Father's Name",
    'address_regional': 'Address (Regional)',
    'driving_license_number': 'DL Number',
    'blood_group': 'Blood Group',
    'organ_donor': 'Organ Donor',
    'validity_date': 'Valid Until',
    'issue_date': 'Issue Date',
    'driving_license': 'Driving License'
  };
  
  if (customLabels[fieldType]) {
    return customLabels[fieldType];
  }
  
  return fieldType
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function getInitials(name) {
  return name
    .split(' ')
    .map(word => word.charAt(0).toUpperCase())
    .slice(0, 2)
    .join('');
}

function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => notification.remove(), 3000);
}
// Load manage data view
async function loadManageData() {
  if (!elements.manageDataList) return;
  
  elements.manageDataList.innerHTML = '<div class="loading">Loading...</div>';
  
  try {
    const response = await sendMessage({ type: 'GET_PROFILE_DATA' });
    
    if (response.success && response.data.entity_details && response.data.entity_details.length > 0) {
      const entityDetails = response.data.entity_details;
      let html = '';
      
      for (const entity of entityDetails) {
        html += `
          <div class="manage-data-item" data-entity-id="${entity.id}">
            <div class="data-info">
              <span class="data-label">${formatFieldName(entity.entity_type)}</span>
              <span class="data-value" data-value="${entity.full_value}">${entity.value}</span>
            </div>
            <div class="data-actions">
              <button class="btn-edit-item" data-entity-id="${entity.id}" title="Edit this field">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                </svg>
              </button>
              <button class="btn-delete-item" data-entity-id="${entity.id}" title="Delete this field">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                </svg>
              </button>
            </div>
          </div>
        `;
      }
      
      elements.manageDataList.innerHTML = html;
      
      // Add edit listeners
      document.querySelectorAll('.btn-edit-item').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const entityId = e.currentTarget.dataset.entityId;
          await handleEditEntity(entityId);
        });
      });
      
      // Add delete listeners
      document.querySelectorAll('.btn-delete-item').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const entityId = e.currentTarget.dataset.entityId;
          await handleDeleteEntity(entityId);
        });
      });
    } else {
      elements.manageDataList.innerHTML = '<p class="no-data">No data saved yet.</p>';
    }
  } catch (error) {
    console.error('Load manage data error:', error);
    elements.manageDataList.innerHTML = '<p class="error">Failed to load data.</p>';
  }
}

// Handle edit entity
async function handleEditEntity(entityId) {
  const item = document.querySelector(`[data-entity-id="${entityId}"]`);
  if (!item) return;
  
  const valueSpan = item.querySelector('.data-value');
  const currentValue = valueSpan.dataset.value;
  const label = item.querySelector('.data-label').textContent;
  
  // Create edit input
  const newValue = prompt(`Edit ${label}:`, currentValue);
  
  if (newValue === null || newValue === currentValue) {
    return; // Cancelled or no change
  }
  
  if (!newValue.trim()) {
    showNotification('Value cannot be empty', 'error');
    return;
  }
  
  try {
    const token = await getAuthToken();
    const response = await fetch(`http://localhost:8000/user/data/entity/${entityId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ new_value: newValue.trim() })
    });
    
    if (response.ok) {
      showNotification('Updated successfully', 'success');
      await loadManageData();
      await loadProfileData();
    } else {
      const error = await response.json();
      showNotification(error.detail || 'Failed to update', 'error');
    }
  } catch (error) {
    console.error('Edit entity error:', error);
    showNotification('Failed to update field', 'error');
  }
}

// Handle delete entity
async function handleDeleteEntity(entityId) {
  const item = document.querySelector(`[data-entity-id="${entityId}"]`);
  if (!item) return;
  
  const label = item.querySelector('.data-label').textContent;
  
  if (!confirm(`Are you sure you want to delete ${label}?`)) {
    return;
  }
  
  try {
    const token = await getAuthToken();
    const response = await fetch(`http://localhost:8000/user/data/entity/${entityId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      showNotification(`${label} deleted successfully`, 'success');
      await loadManageData();
      await loadProfileData();
    } else {
      const error = await response.json();
      showNotification(error.detail || 'Failed to delete', 'error');
    }
  } catch (error) {
    console.error('Delete entity error:', error);
    showNotification('Failed to delete field', 'error');
  }
}

// Handle delete single field (legacy - keeping for backward compatibility)
async function handleDeleteField(fieldType) {
  if (!confirm(`Are you sure you want to delete your ${formatFieldName(fieldType)}?`)) {
    return;
  }
  
  try {
    const token = await getAuthToken();
    const response = await fetch(`http://localhost:8000/user/data/field/${fieldType}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      showNotification(`${formatFieldName(fieldType)} deleted successfully`, 'success');
      await loadManageData();
      await loadProfileData();
    } else {
      showNotification('Failed to delete field', 'error');
    }
  } catch (error) {
    console.error('Delete field error:', error);
    showNotification('Failed to delete field', 'error');
  }
}

// Handle delete all data
async function handleDeleteAllData() {
  if (!confirm('⚠️ Are you sure you want to delete ALL your saved data? This action cannot be undone!')) {
    return;
  }
  
  if (!confirm('This will permanently delete all your documents and extracted information. Continue?')) {
    return;
  }
  
  try {
    const token = await getAuthToken();
    const response = await fetch('http://127.0.0.1:8000/user/data?confirm=true', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      showNotification('All data deleted successfully', 'success');
      showSection('main');
      loadProfileData();
    } else {
      const error = await response.json();
      showNotification(error.detail || 'Failed to delete data', 'error');
    }
  } catch (error) {
    console.error('Delete all data error:', error);
    showNotification('Failed to delete data', 'error');
  }
}

// ======================
// DigiLocker Integration
// ======================

// Check DigiLocker connection status
async function checkDigiLockerStatus() {
  try {
    const token = await getAuthToken();
    const response = await fetch('http://127.0.0.1:8000/digilocker/status', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      currentState.digilockerConnected = data.connected;
      updateDigiLockerUI(data);
    }
  } catch (error) {
    console.error('DigiLocker status check error:', error);
  }
}

// Update DigiLocker UI based on connection status
function updateDigiLockerUI(status) {
  if (!elements.digilockerStatus) return;
  
  if (status.connected) {
    elements.digilockerStatus.textContent = `Connected as ${status.name || 'User'}`;
    elements.digilockerStatus.classList.add('connected');
    elements.digilockerConnectBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
      </svg>
      Connected
    `;
    elements.digilockerConnectBtn.disabled = true;
    elements.digilockerImportBtn.classList.remove('hidden');
  } else {
    elements.digilockerStatus.textContent = 'Not Connected';
    elements.digilockerStatus.classList.remove('connected');
    elements.digilockerConnectBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
      </svg>
      Connect DigiLocker
    `;
    elements.digilockerConnectBtn.disabled = false;
    elements.digilockerImportBtn.classList.add('hidden');
  }
}

// Handle DigiLocker connect button click
async function handleDigiLockerConnect() {
  try {
    showNotification('Connecting to DigiLocker...', 'info');
    
    const token = await getAuthToken();
    const response = await fetch('http://127.0.0.1:8000/digilocker/auth/initiate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        redirect_url: chrome.runtime.getURL('popup/digilocker-callback.html')
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      
      // Store state for callback verification
      await chrome.storage.local.set({ 
        digilocker_state: data.state,
        digilocker_auth_pending: true
      });
      
      // Open DigiLocker auth in new tab
      chrome.tabs.create({ url: data.auth_url });
      
      showNotification('Complete login in DigiLocker tab', 'info');
    } else {
      const error = await response.json();
      showNotification(error.detail || 'Failed to initiate DigiLocker connection', 'error');
    }
  } catch (error) {
    console.error('DigiLocker connect error:', error);
    showNotification('Failed to connect to DigiLocker', 'error');
  }
}

// Load documents from DigiLocker
async function loadDigiLockerDocuments() {
  if (!elements.digilockerDocsList) return;
  
  elements.digilockerDocsList.innerHTML = '<div class="loading">Loading documents from DigiLocker...</div>';
  currentState.selectedDigilockerDocs = [];
  updateImportButtonState();
  
  try {
    const token = await getAuthToken();
    const response = await fetch('http://127.0.0.1:8000/digilocker/documents', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      
      if (data.success && data.documents.length > 0) {
        currentState.digilockerDocs = data.documents;
        renderDigiLockerDocuments(data.documents);
      } else if (data.documents.length === 0) {
        elements.digilockerDocsList.innerHTML = `
          <div class="empty-state">
            <p>No documents found in your DigiLocker.</p>
            <p class="hint">Upload documents to DigiLocker first, then import them here.</p>
          </div>
        `;
      } else {
        elements.digilockerDocsList.innerHTML = `
          <div class="error-state">
            <p>${data.error || 'Failed to load documents'}</p>
          </div>
        `;
      }
    } else {
      const error = await response.json();
      elements.digilockerDocsList.innerHTML = `
        <div class="error-state">
          <p>${error.detail || 'Failed to fetch documents'}</p>
        </div>
      `;
    }
  } catch (error) {
    console.error('Load DigiLocker docs error:', error);
    elements.digilockerDocsList.innerHTML = `
      <div class="error-state">
        <p>Failed to connect to server</p>
      </div>
    `;
  }
}

// Render DigiLocker documents list
function renderDigiLockerDocuments(documents) {
  let html = '';
  
  documents.forEach((doc, index) => {
    const docTypeLabel = formatFieldName(doc.doc_type);
    html += `
      <div class="digilocker-doc-item" data-uri="${doc.uri}" data-index="${index}">
        <input type="checkbox" class="digilocker-doc-checkbox" id="doc-${index}">
        <div class="digilocker-doc-info">
          <div class="digilocker-doc-name">${doc.name}</div>
          <div class="digilocker-doc-type">${docTypeLabel}</div>
          <div class="digilocker-doc-issuer">${doc.issuer_name}</div>
        </div>
      </div>
    `;
  });
  
  elements.digilockerDocsList.innerHTML = html;
  
  // Add click handlers
  document.querySelectorAll('.digilocker-doc-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (e.target.type !== 'checkbox') {
        const checkbox = item.querySelector('.digilocker-doc-checkbox');
        checkbox.checked = !checkbox.checked;
      }
      item.classList.toggle('selected', item.querySelector('.digilocker-doc-checkbox').checked);
      updateSelectedDocuments();
    });
  });
}

// Update selected documents list
function updateSelectedDocuments() {
  currentState.selectedDigilockerDocs = [];
  
  document.querySelectorAll('.digilocker-doc-item.selected').forEach(item => {
    const uri = item.dataset.uri;
    const doc = currentState.digilockerDocs.find(d => d.uri === uri);
    if (doc) {
      currentState.selectedDigilockerDocs.push(doc);
    }
  });
  
  updateImportButtonState();
}

// Update import button state
function updateImportButtonState() {
  if (!elements.importSelectedBtn) return;
  
  const count = currentState.selectedDigilockerDocs.length;
  elements.importSelectedBtn.disabled = count === 0;
  elements.importSelectedBtn.textContent = `Import Selected (${count})`;
}

// Handle import selected documents
async function handleImportSelectedDocuments() {
  if (currentState.selectedDigilockerDocs.length === 0) {
    showNotification('Please select documents to import', 'error');
    return;
  }
  
  elements.importSelectedBtn.disabled = true;
  elements.importSelectedBtn.textContent = 'Importing...';
  
  try {
    const token = await getAuthToken();
    const uris = currentState.selectedDigilockerDocs.map(d => d.uri);
    
    const response = await fetch('http://127.0.0.1:8000/digilocker/import', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ document_uris: uris })
    });
    
    if (response.ok) {
      const data = await response.json();
      
      if (data.success) {
        showNotification(`Successfully imported ${data.imported} document(s)`, 'success');
        showSection('main');
        loadProfileData();
      } else {
        showNotification(data.error || 'Import failed', 'error');
      }
    } else {
      const error = await response.json();
      showNotification(error.detail || 'Failed to import documents', 'error');
    }
  } catch (error) {
    console.error('Import documents error:', error);
    showNotification('Failed to import documents', 'error');
  } finally {
    updateImportButtonState();
  }
}

// Listen for DigiLocker callback
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local' && changes.digilocker_connected) {
    if (changes.digilocker_connected.newValue) {
      showNotification('DigiLocker connected successfully!', 'success');
      checkDigiLockerStatus();
    }
  }
});