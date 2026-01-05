/**
 * AI Form Filling Assistant - Content Script
 * Detects forms, handles autofill, and manages user interactions on government websites
 */

(function() {
  'use strict';
  
  // Prevent multiple injections
  if (window.__formAssistantInjected) return;
  window.__formAssistantInjected = true;
  
  // Configuration
  const CONFIG = {
    highlightColor: '#4CAF50',
    highlightBorderColor: '#2E7D32',
    buttonColor: '#1976D2'
  };
  
  // Field mapping for common government form fields
  const FIELD_MAPPING = {
    // Name fields
    'name': ['name', 'full_name', 'fullname', 'applicant_name', 'applicantname'],
    'full_name': ['name', 'full_name', 'fullname', 'applicant_name'],
    'father_name': ['father_name', 'fathername', 'father', 'guardian_name', 'father_husband'],
    
    // Identity fields
    'aadhaar_number': ['aadhaar', 'aadhar', 'aadhaar_no', 'uid', 'uidai'],
    'pan_number': ['pan', 'pan_no', 'pancard', 'pan_number'],
    'voter_id_number': ['voter_id', 'voterid', 'epic', 'epic_no'],
    
    // Personal details
    'date_of_birth': ['dob', 'date_of_birth', 'dateofbirth', 'birth_date', 'birthdate'],
    'gender': ['gender', 'sex'],
    'address': ['address', 'full_address', 'residential_address', 'permanent_address'],
    
    // Contact details (from user login)
    'mobile_number': ['mobile', 'mobile_no', 'mobile_number', 'phone', 'phone_no', 'phone_number', 'contact', 'contact_no', 'cell'],
    'email': ['email', 'email_id', 'emailid', 'mail', 'mail_id', 'email_address'],
    
    // Other
    'community': ['community', 'caste', 'category'],
    'annual_income': ['income', 'annual_income', 'yearly_income']
  };
  
  // State
  let detectedFields = [];
  let autofillData = null;
  let isAutofillActive = false;
  
  // Initialize
  function init() {
    // Check if current page is HTTPS
    if (window.location.protocol !== 'https:') {
      console.log('Form Assistant: Only HTTPS pages supported');
      return;
    }
    
    // Detect forms after page load
    setTimeout(detectForms, 1000);
    
    // Listen for messages from popup/background
    chrome.runtime.onMessage.addListener(handleMessage);
    
    // Observe DOM changes for dynamically loaded forms
    observeDOMChanges();
  }
  
  // Handle messages from popup/background
  function handleMessage(message, sender, sendResponse) {
    switch (message.type) {
      case 'DETECT_FORMS':
        const forms = detectForms();
        sendResponse({ success: true, data: { forms: forms.length, fields: detectedFields } });
        break;
      
      case 'AUTOFILL_FORM':
        performAutofill(message.payload.data);
        sendResponse({ success: true });
        break;
      
      case 'SHOW_PREVIEW':
        showPreviewPopup(message.payload.data);
        sendResponse({ success: true });
        break;
      
      case 'APPLY_VOICE_INPUT':
        applyVoiceInput(message.payload);
        sendResponse({ success: true });
        break;
      
      default:
        sendResponse({ success: false, error: 'Unknown message type' });
    }
    return true;
  }
  
  // Detect forms on the page
  function detectForms() {
    const forms = document.querySelectorAll('form');
    detectedFields = [];
    
    forms.forEach(form => {
      const inputs = form.querySelectorAll('input, select, textarea');
      
      inputs.forEach(input => {
        const fieldInfo = identifyField(input);
        if (fieldInfo) {
          detectedFields.push({
            element: input,
            ...fieldInfo
          });
        }
      });
    });
    
    // Also check for inputs outside forms
    const standaloneInputs = document.querySelectorAll('input:not(form input), select:not(form select)');
    standaloneInputs.forEach(input => {
      const fieldInfo = identifyField(input);
      if (fieldInfo) {
        detectedFields.push({
          element: input,
          ...fieldInfo
        });
      }
    });
    
    if (detectedFields.length > 0) {
      showAutofillButton();
    }
    
    console.log(`Form Assistant: Detected ${detectedFields.length} fillable fields`);
    return forms;
  }
  
  // Identify what type of field an input is
  function identifyField(input) {
    if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') {
      return null;
    }
    
    // Get identifiers
    const name = (input.name || '').toLowerCase();
    const id = (input.id || '').toLowerCase();
    const placeholder = (input.placeholder || '').toLowerCase();
    const label = getFieldLabel(input).toLowerCase();
    const ariaLabel = (input.getAttribute('aria-label') || '').toLowerCase();
    
    const identifiers = [name, id, placeholder, label, ariaLabel].filter(Boolean);
    
    // Match against known field types
    for (const [fieldType, patterns] of Object.entries(FIELD_MAPPING)) {
      for (const pattern of patterns) {
        for (const identifier of identifiers) {
          if (identifier.includes(pattern) || pattern.includes(identifier)) {
            return {
              fieldType,
              identifier: name || id,
              label: label || placeholder || name || id
            };
          }
        }
      }
    }
    
    return null;
  }
  
  // Get label text for a field
  function getFieldLabel(input) {
    // Check for associated label
    if (input.id) {
      const label = document.querySelector(`label[for="${input.id}"]`);
      if (label) return label.textContent.trim();
    }
    
    // Check parent label
    const parentLabel = input.closest('label');
    if (parentLabel) return parentLabel.textContent.trim();
    
    // Check preceding sibling
    const prev = input.previousElementSibling;
    if (prev && (prev.tagName === 'LABEL' || prev.tagName === 'SPAN')) {
      return prev.textContent.trim();
    }
    
    return '';
  }
  
  // Show autofill button
  function showAutofillButton() {
    // Remove existing button if any
    const existing = document.getElementById('form-assistant-btn');
    if (existing) existing.remove();
    
    const button = document.createElement('button');
    button.id = 'form-assistant-btn';
    button.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14H6v-2h6v2zm4-4H6v-2h10v2zm0-4H6V7h10v2z"/>
      </svg>
      <span>Autofill Form</span>
    `;
    button.className = 'form-assistant-btn';
    button.onclick = handleAutofillClick;
    
    document.body.appendChild(button);
  }
  
  // Handle autofill button click
  async function handleAutofillClick() {
    // Send message to get autofill data
    const fields = detectedFields.map(f => f.fieldType);
    
    chrome.runtime.sendMessage({
      type: 'GET_AUTOFILL_DATA',
      payload: {
        fields: [...new Set(fields)], // Unique fields
        websiteUrl: window.location.href
      }
    }, response => {
      if (response.success) {
        showConsentPopup(response.data.fields);
      } else {
        showNotification(response.error || 'Failed to get autofill data', 'error');
      }
    });
  }
  
  // Show consent popup before autofill
  function showConsentPopup(data) {
    // Remove existing popup
    const existing = document.getElementById('form-assistant-popup');
    if (existing) existing.remove();
    
    const popup = document.createElement('div');
    popup.id = 'form-assistant-popup';
    popup.className = 'form-assistant-popup';
    
    // Generate field preview
    let fieldsHtml = '';
    for (const [field, value] of Object.entries(data)) {
      fieldsHtml += `
        <div class="field-preview">
          <label>${formatFieldName(field)}</label>
          <span class="field-value">${maskSensitiveValue(field, value)}</span>
        </div>
      `;
    }
    
    popup.innerHTML = `
      <div class="popup-header">
        <h3>🤖 AI Form Assistant</h3>
        <button class="close-btn" onclick="this.closest('.form-assistant-popup').remove()">×</button>
      </div>
      <div class="popup-content">
        <p>Do you want to autofill this form with your saved data?</p>
        <div class="fields-preview">
          ${fieldsHtml}
        </div>
        <div class="consent-notice">
          <input type="checkbox" id="consent-check">
          <label for="consent-check">I consent to autofilling this form with my verified data</label>
        </div>
      </div>
      <div class="popup-actions">
        <button class="btn-secondary" onclick="this.closest('.form-assistant-popup').remove()">Cancel</button>
        <button class="btn-primary" id="confirm-autofill-btn">Autofill Form</button>
      </div>
    `;
    
    document.body.appendChild(popup);
    
    // Store data for autofill
    autofillData = data;
    
    // Handle confirm button
    document.getElementById('confirm-autofill-btn').onclick = () => {
      const consentCheck = document.getElementById('consent-check');
      if (!consentCheck.checked) {
        showNotification('Please provide consent to continue', 'warning');
        return;
      }
      
      popup.remove();
      performAutofill(data);
    };
  }
  
  // Perform the actual autofill
  function performAutofill(data) {
    let filledCount = 0;
    
    detectedFields.forEach(field => {
      const value = data[field.fieldType];
      if (value) {
        fillField(field.element, value, field.fieldType);
        highlightField(field.element);
        filledCount++;
      }
    });
    
    isAutofillActive = true;
    
    showNotification(`Filled ${filledCount} fields. Please review before submitting.`, 'success');
    
    // Show pre-submission verification
    addSubmitInterceptor();
    
    // Log consent
    chrome.runtime.sendMessage({
      type: 'LOG_CONSENT',
      payload: {
        action: 'autofill_request',
        consentGiven: true,
        targetWebsite: window.location.href,
        formFields: Object.keys(data)
      }
    });
  }
  
  // Fill a single field
  function fillField(element, value, fieldType = null) {
    if (element.tagName === 'SELECT') {
      // Handle select dropdowns
      const options = Array.from(element.options);
      
      // For date-related selects, handle month names
      if (fieldType === 'date_of_birth' || isDateRelatedSelect(element)) {
        const dateVal = parseDate(value);
        if (dateVal) {
          // Check if this select is for day, month, or year
          const selectPurpose = detectSelectPurpose(element, options);
          if (selectPurpose === 'day') {
            const dayMatch = options.find(opt => parseInt(opt.value) === dateVal.day || parseInt(opt.text) === dateVal.day);
            if (dayMatch) element.value = dayMatch.value;
          } else if (selectPurpose === 'month') {
            // Month select - could be number (1-12) or name (Jan-Dec)
            const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
            const monthMatch = options.find(opt => {
              const val = opt.value.toLowerCase();
              const txt = opt.text.toLowerCase();
              return parseInt(opt.value) === dateVal.month || 
                     parseInt(opt.text) === dateVal.month ||
                     val.includes(monthNames[dateVal.month - 1]) ||
                     txt.includes(monthNames[dateVal.month - 1]);
            });
            if (monthMatch) element.value = monthMatch.value;
          } else if (selectPurpose === 'year') {
            const yearMatch = options.find(opt => parseInt(opt.value) === dateVal.year || parseInt(opt.text) === dateVal.year);
            if (yearMatch) element.value = yearMatch.value;
          } else {
            // Generic select - try value matching
            const match = options.find(opt => 
              opt.value.toLowerCase() === value.toLowerCase() ||
              opt.text.toLowerCase() === value.toLowerCase()
            );
            if (match) element.value = match.value;
          }
          element.dispatchEvent(new Event('change', { bubbles: true }));
          return;
        }
      }
      
      // Standard select handling
      const match = options.find(opt => 
        opt.value.toLowerCase() === value.toLowerCase() ||
        opt.text.toLowerCase() === value.toLowerCase()
      );
      if (match) {
        element.value = match.value;
      }
    } else if (element.type === 'radio' || element.type === 'checkbox') {
      // Handle radio/checkbox
      if (element.value.toLowerCase() === value.toLowerCase()) {
        element.checked = true;
      }
    } else if (element.type === 'date') {
      // HTML5 date input expects YYYY-MM-DD
      const dateVal = parseDate(value);
      if (dateVal) {
        const formatted = `${dateVal.year}-${String(dateVal.month).padStart(2, '0')}-${String(dateVal.day).padStart(2, '0')}`;
        element.value = formatted;
      } else {
        element.value = value;
      }
    } else {
      // Handle text inputs - check if it's a date field
      if (fieldType === 'date_of_birth' || isDateField(element)) {
        const dateVal = parseDate(value);
        if (dateVal) {
          // Detect expected format from placeholder or existing value pattern
          const expectedFormat = detectDateFormat(element);
          element.value = formatDateToExpected(dateVal, expectedFormat);
        } else {
          element.value = value;
        }
      } else {
        // Handle text inputs
        element.value = value;
      }
    }
    
    // Trigger change event
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  }
  
  // Parse date from various formats (DD/MM/YYYY, DD-MM-YYYY, etc.)
  function parseDate(dateStr) {
    if (!dateStr) return null;
    
    // Handle year-only format (e.g., "1990")
    const yearOnlyMatch = dateStr.match(/^(\d{4})$/);
    if (yearOnlyMatch) {
      return {
        day: 1,
        month: 1,
        year: parseInt(yearOnlyMatch[1]),
        yearOnly: true
      };
    }
    
    // Try DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY (Indian format - day comes first)
    const match = dateStr.match(/^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})$/);
    if (match) {
      const first = parseInt(match[1]);
      const second = parseInt(match[2]);
      const year = parseInt(match[3]);
      
      // In Indian format, day comes first, then month
      // Validate: day should be 1-31, month should be 1-12
      let day, month;
      if (second <= 12) {
        // Standard DD/MM/YYYY format (Indian)
        day = first;
        month = second;
      } else if (first <= 12) {
        // Could be MM/DD/YYYY (American format)
        month = first;
        day = second;
      } else {
        // Both > 12, assume DD/MM format with possible error
        day = first;
        month = Math.min(second, 12);
      }
      
      return { day, month, year };
    }
    
    // Try YYYY-MM-DD (ISO format)
    const isoMatch = dateStr.match(/^(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})$/);
    if (isoMatch) {
      return {
        day: parseInt(isoMatch[3]),
        month: parseInt(isoMatch[2]),
        year: parseInt(isoMatch[1])
      };
    }
    
    return null;
  }
  
  // Check if element is a date field
  function isDateField(element) {
    const name = (element.name || '').toLowerCase();
    const id = (element.id || '').toLowerCase();
    const placeholder = (element.placeholder || '').toLowerCase();
    return name.includes('date') || name.includes('dob') || 
           id.includes('date') || id.includes('dob') ||
           placeholder.includes('date') || placeholder.includes('dd');
  }
  
  // Check if select is date-related
  function isDateRelatedSelect(element) {
    const name = (element.name || '').toLowerCase();
    const id = (element.id || '').toLowerCase();
    return name.includes('day') || name.includes('month') || name.includes('year') ||
           name.includes('date') || name.includes('dob') ||
           id.includes('day') || id.includes('month') || id.includes('year') ||
           id.includes('date') || id.includes('dob');
  }
  
  // Detect what a select is for (day, month, year)
  function detectSelectPurpose(element, options) {
    const name = (element.name || '').toLowerCase();
    const id = (element.id || '').toLowerCase();
    
    if (name.includes('day') || id.includes('day') || name.includes('dd')) return 'day';
    if (name.includes('month') || id.includes('month') || name.includes('mm')) return 'month';
    if (name.includes('year') || id.includes('year') || name.includes('yyyy') || name.includes('yy')) return 'year';
    
    // Detect from options
    const values = options.map(o => o.value || o.text);
    const hasMonthNames = values.some(v => /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i.test(v));
    if (hasMonthNames) return 'month';
    
    // Check numeric ranges
    const numericValues = values.filter(v => /^\d+$/.test(v)).map(v => parseInt(v));
    if (numericValues.length > 0) {
      const max = Math.max(...numericValues);
      if (max <= 31 && max >= 28) return 'day';
      if (max === 12 || max <= 12 && numericValues.length <= 13) return 'month';
      if (max > 1900) return 'year';
    }
    
    return null;
  }
  
  // Detect expected date format from element attributes
  function detectDateFormat(element) {
    const placeholder = (element.placeholder || '').toLowerCase();
    const pattern = element.getAttribute('pattern') || '';
    
    // Check placeholder patterns
    if (placeholder.includes('dd-mmm-yyyy') || placeholder.includes('dd-mon-yyyy')) {
      return 'DD-Mon-YYYY';  // 10-Dec-1990
    }
    if (placeholder.includes('dd/mm/yyyy')) {
      return 'DD/MM/YYYY';
    }
    if (placeholder.includes('dd-mm-yyyy')) {
      return 'DD-MM-YYYY';
    }
    if (placeholder.includes('mm/dd/yyyy')) {
      return 'MM/DD/YYYY';
    }
    if (placeholder.includes('yyyy-mm-dd')) {
      return 'YYYY-MM-DD';
    }
    
    // Default to DD/MM/YYYY (common in India)
    return 'DD/MM/YYYY';
  }
  
  // Format date to expected format
  function formatDateToExpected(dateObj, format) {
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const day = String(dateObj.day).padStart(2, '0');
    const month = String(dateObj.month).padStart(2, '0');
    const year = dateObj.year;
    const monthName = monthNames[dateObj.month - 1];
    
    switch (format) {
      case 'DD-Mon-YYYY':
        return `${day}-${monthName}-${year}`;
      case 'DD/MM/YYYY':
        return `${day}/${month}/${year}`;
      case 'DD-MM-YYYY':
        return `${day}-${month}-${year}`;
      case 'MM/DD/YYYY':
        return `${month}/${day}/${year}`;
      case 'YYYY-MM-DD':
        return `${year}-${month}-${day}`;
      default:
        return `${day}/${month}/${year}`;
    }
  }
  
  // Highlight filled field
  function highlightField(element) {
    element.classList.add('form-assistant-filled');
    element.style.setProperty('border-color', CONFIG.highlightBorderColor, 'important');
    element.style.setProperty('background-color', `${CONFIG.highlightColor}15`, 'important');
  }
  
  // Add interceptor for form submission
  function addSubmitInterceptor() {
    document.querySelectorAll('form').forEach(form => {
      form.addEventListener('submit', handleFormSubmit, true);
    });
    
    // Also intercept submit buttons
    document.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(btn => {
      btn.addEventListener('click', handleFormSubmit, true);
    });
  }
  
  // Handle form submission - show verification popup
  function handleFormSubmit(event) {
    if (!isAutofillActive) return;
    
    event.preventDefault();
    event.stopPropagation();
    
    showSubmissionVerification(event.target);
  }
  
  // Show pre-submission verification popup
  function showSubmissionVerification(form) {
    const existing = document.getElementById('form-assistant-verify');
    if (existing) existing.remove();
    
    // Collect filled values
    let fieldsHtml = '';
    detectedFields.forEach(field => {
      if (field.element.value) {
        fieldsHtml += `
          <div class="verify-field">
            <label>${field.label || field.fieldType}</label>
            <span>${maskSensitiveValue(field.fieldType, field.element.value)}</span>
          </div>
        `;
      }
    });
    
    const popup = document.createElement('div');
    popup.id = 'form-assistant-verify';
    popup.className = 'form-assistant-popup verification-popup';
    
    popup.innerHTML = `
      <div class="popup-header verification-header">
        <h3>⚠️ Verify Before Submitting</h3>
      </div>
      <div class="popup-content">
        <p><strong>Please review the filled data before submitting:</strong></p>
        <div class="verify-fields">
          ${fieldsHtml}
        </div>
        <div class="warning-notice">
          <p>Make sure all information is correct. You are responsible for the accuracy of submitted data.</p>
        </div>
      </div>
      <div class="popup-actions">
        <button class="btn-secondary" id="cancel-submit-btn">Go Back & Edit</button>
        <button class="btn-primary btn-submit" id="confirm-submit-btn">Confirm & Submit</button>
      </div>
    `;
    
    document.body.appendChild(popup);
    
    // Handle cancel
    document.getElementById('cancel-submit-btn').onclick = () => {
      popup.remove();
    };
    
    // Handle confirm
    document.getElementById('confirm-submit-btn').onclick = () => {
      popup.remove();
      isAutofillActive = false;
      
      // Log consent for submission
      chrome.runtime.sendMessage({
        type: 'LOG_CONSENT',
        payload: {
          action: 'form_submission',
          consentGiven: true,
          targetWebsite: window.location.href,
          formFields: detectedFields.map(f => f.fieldType)
        }
      });
      
      // Remove interceptor and submit
      if (form.tagName === 'FORM') {
        form.removeEventListener('submit', handleFormSubmit, true);
        form.submit();
      } else {
        form.closest('form')?.submit();
      }
    };
  }
  
  // Apply voice input to field
  function applyVoiceInput({ fieldType, value }) {
    const field = detectedFields.find(f => f.fieldType === fieldType);
    if (field) {
      fillField(field.element, value);
      highlightField(field.element);
      showNotification(`Voice input applied to ${formatFieldName(fieldType)}`, 'success');
    }
  }
  
  // Show notification
  function showNotification(message, type = 'info') {
    const existing = document.querySelector('.form-assistant-notification');
    if (existing) existing.remove();
    
    const notification = document.createElement('div');
    notification.className = `form-assistant-notification ${type}`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => notification.remove(), 4000);
  }
  
  // Observe DOM changes for dynamic content
  function observeDOMChanges() {
    const observer = new MutationObserver(mutations => {
      let hasNewForms = false;
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === 1) {
            if (node.tagName === 'FORM' || node.querySelector?.('form, input')) {
              hasNewForms = true;
            }
          }
        });
      });
      
      if (hasNewForms) {
        setTimeout(detectForms, 500);
      }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
  }
  
  // Utility: Format field name for display
  function formatFieldName(fieldType) {
    return fieldType
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
  
  // Utility: Mask sensitive values for display
  function maskSensitiveValue(fieldType, value) {
    const sensitiveFields = ['aadhaar_number', 'pan_number', 'voter_id_number'];
    
    if (sensitiveFields.includes(fieldType) && value.length > 4) {
      return 'X'.repeat(value.length - 4) + value.slice(-4);
    }
    
    return value;
  }
  
  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
