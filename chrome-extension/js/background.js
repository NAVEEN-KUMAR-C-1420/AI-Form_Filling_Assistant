/**
 * AI Form Filling Assistant - Background Service Worker
 * Handles API communication, authentication, and extension state
 */

// API Configuration
const API_BASE_URL = 'http://localhost:8000';  // Change to production URL

// State management
let authState = {
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false
};

// Initialize extension on install
chrome.runtime.onInstalled.addListener(async () => {
  console.log('AI Form Filling Assistant installed');
  await loadAuthState();
});

// Also load auth state when service worker starts (browser restart, etc.)
chrome.runtime.onStartup.addListener(async () => {
  console.log('AI Form Filling Assistant starting up');
  await loadAuthState();
});

// Load auth state immediately when script loads
(async () => {
  await loadAuthState();
  console.log('Auth state loaded on script init:', authState.isAuthenticated);
})();

// Load auth state from storage
async function loadAuthState() {
  try {
    const data = await chrome.storage.local.get(['authState']);
    if (data.authState) {
      authState = data.authState;
    }
  } catch (error) {
    console.error('Error loading auth state:', error);
  }
}

// Save auth state to storage
async function saveAuthState() {
  try {
    await chrome.storage.local.set({ authState });
  } catch (error) {
    console.error('Error saving auth state:', error);
  }
}

// API request helper
async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };
  
  // Add auth header if authenticated
  if (authState.accessToken) {
    headers['Authorization'] = `Bearer ${authState.accessToken}`;
  }
  
  try {
    const response = await fetch(url, {
      ...options,
      headers
    });
    
    // Handle token refresh if needed
    if (response.status === 401 && authState.refreshToken) {
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        // Retry original request
        headers['Authorization'] = `Bearer ${authState.accessToken}`;
        return fetch(url, { ...options, headers });
      }
    }
    
    return response;
  } catch (error) {
    console.error('API request error:', error);
    throw error;
  }
}

// Refresh access token
async function refreshAccessToken() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: authState.refreshToken })
    });
    
    if (response.ok) {
      const data = await response.json();
      authState.accessToken = data.access_token;
      authState.refreshToken = data.refresh_token;
      await saveAuthState();
      return true;
    }
  } catch (error) {
    console.error('Token refresh error:', error);
  }
  
  // Clear auth state on refresh failure
  await logout();
  return false;
}

// Message handler for popup and content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender).then(sendResponse);
  return true; // Keep channel open for async response
});

async function handleMessage(message, sender) {
  switch (message.type) {
    case 'LOGIN':
      return await handleLogin(message.payload);
    
    case 'SIGNUP':
      return await handleSignup(message.payload);
    
    case 'LOGOUT':
      return await logout();
    
    case 'GET_AUTH_STATE':
      return { success: true, data: { isAuthenticated: authState.isAuthenticated, user: authState.user } };
    
    case 'GET_PROFILE_DATA':
      return await getProfileData();
    
    case 'GET_AUTOFILL_DATA':
      return await getAutofillData(message.payload);
    
    case 'LOG_CONSENT':
      return await logConsent(message.payload);
    
    case 'CHECK_WEBSITE':
      return checkWebsite(message.payload.url);
    
    case 'PROCESS_VOICE':
      return await processVoiceInput(message.payload);
    
    default:
      return { success: false, error: 'Unknown message type' };
  }
}

// Handle login
async function handleLogin({ email, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      const error = await response.json();
      return { success: false, error: error.detail || 'Login failed' };
    }
    
    const tokens = await response.json();
    authState.accessToken = tokens.access_token;
    authState.refreshToken = tokens.refresh_token;
    authState.isAuthenticated = true;
    
    // Get user profile
    const userResponse = await apiRequest('/user/me');
    if (userResponse.ok) {
      authState.user = await userResponse.json();
    }
    
    await saveAuthState();
    
    return { success: true, data: { user: authState.user } };
  } catch (error) {
    console.error('Login error:', error);
    return { success: false, error: 'Network error. Please try again.' };
  }
}

// Handle signup
async function handleSignup({ email, password, full_name, phone_number }) {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name, phone_number })
    });
    
    if (!response.ok) {
      const error = await response.json();
      return { success: false, error: error.detail || 'Registration failed' };
    }
    
    const userData = await response.json();
    
    // After successful registration, automatically login the user
    const loginResponse = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!loginResponse.ok) {
      // Registration succeeded but login failed - still return success
      return { success: true, data: { user: userData, autoLogin: false } };
    }
    
    const tokens = await loginResponse.json();
    authState.accessToken = tokens.access_token;
    authState.refreshToken = tokens.refresh_token;
    authState.isAuthenticated = true;
    authState.user = userData;
    
    await saveAuthState();
    
    return { success: true, data: { user: userData, autoLogin: true } };
  } catch (error) {
    console.error('Signup error:', error);
    return { success: false, error: 'Network error. Please try again.' };
  }
}

// Handle logout
async function logout() {
  authState = {
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false
  };
  await saveAuthState();
  return { success: true };
}

// Get profile data
async function getProfileData() {
  if (!authState.isAuthenticated) {
    return { success: false, error: 'Not authenticated' };
  }
  
  try {
    const response = await apiRequest('/user/profile-data');
    if (response.ok) {
      const data = await response.json();
      return { success: true, data };
    }
    return { success: false, error: 'Failed to fetch profile data' };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Get autofill data for specific fields
async function getAutofillData({ fields, websiteUrl }) {
  if (!authState.isAuthenticated) {
    return { success: false, error: 'Not authenticated' };
  }
  
  // Verify HTTPS
  if (!websiteUrl.startsWith('https://')) {
    return { success: false, error: 'Only HTTPS websites are supported' };
  }
  
  try {
    const response = await apiRequest('/user/autofill', {
      method: 'POST',
      body: JSON.stringify({ fields, website_url: websiteUrl })
    });
    
    if (response.ok) {
      const data = await response.json();
      return { success: true, data };
    }
    return { success: false, error: 'Failed to fetch autofill data' };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Log consent action
async function logConsent({ action, consentGiven, targetWebsite, formFields }) {
  if (!authState.isAuthenticated) {
    return { success: false, error: 'Not authenticated' };
  }
  
  try {
    const response = await apiRequest('/user/consent-history', {
      method: 'POST',
      body: JSON.stringify({
        action,
        consent_given: consentGiven,
        target_website: targetWebsite,
        form_fields: formFields
      })
    });
    
    return { success: response.ok };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Check if website is supported for autofill
function checkWebsite(url) {
  const supportedDomains = [
    'gov.in',
    'india.gov.in',
    'digitalindia.gov.in',
    'uidai.gov.in',
    'incometax.gov.in',
    'epfindia.gov.in'
  ];
  
  try {
    const urlObj = new URL(url);
    
    // Must be HTTPS
    if (urlObj.protocol !== 'https:') {
      return { success: true, data: { supported: false, reason: 'Only HTTPS websites are supported' } };
    }
    
    // Check domain
    const hostname = urlObj.hostname;
    const isSupported = supportedDomains.some(domain => hostname.endsWith(domain));
    
    return {
      success: true,
      data: {
        supported: isSupported,
        reason: isSupported ? 'Website supported' : 'Website not in supported list'
      }
    };
  } catch (error) {
    return { success: false, error: 'Invalid URL' };
  }
}

// Process voice input
async function processVoiceInput({ audioData, language, targetField }) {
  if (!authState.isAuthenticated) {
    return { success: false, error: 'Not authenticated' };
  }
  
  try {
    const response = await apiRequest('/voice-input', {
      method: 'POST',
      body: JSON.stringify({
        audio_data: audioData,
        language,
        target_field: targetField
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      return { success: true, data };
    }
    
    const error = await response.json();
    return { success: false, error: error.detail || 'Voice processing failed' };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Listen for tab updates to detect form pages
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    const result = checkWebsite(tab.url);
    if (result.success && result.data.supported) {
      // Inject content script if not already
      chrome.scripting.executeScript({
        target: { tabId },
        files: ['js/content.js']
      }).catch(() => {
        // Script might already be injected
      });
    }
  }
});
