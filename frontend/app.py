"""
Frontend Application for Marketing Automation System
Implements login authentication and dashboard UI
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import random
import re
import secrets
import requests
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Backend API configuration
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:5001')

# Mock users database (for demo purposes)
MOCK_USERS = {
    "demo@demo.com": {
        "password": "demo123",
        "2fa_enabled": True,
        "phone": "Ending with 3270",
        "backup_email": "***er@demo.com"
    },
    "admin@marketing.com": {
        "password": "admin123",
        "2fa_enabled": False,
        "phone": "",
        "backup_email": ""
    }
}


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main login page"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    """Handle login request"""
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not validate_email(email):
        return jsonify({'success': False, 'message': 'Invalid email format'}), 400
    
    if email in MOCK_USERS and MOCK_USERS[email]['password'] == password:
        user = MOCK_USERS[email]
        
        if user.get('2fa_enabled', False):
            session['pending_2fa_user'] = email
            return jsonify({
                'success': True,
                'requires_2fa': True,
                'phone': user['phone'],
                'backup_email': user['backup_email']
            })
        else:
            session['user'] = email
            return jsonify({'success': True, 'requires_2fa': False})
    else:
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401


@app.route('/2fa')
def two_factor():
    """2FA verification page"""
    if 'pending_2fa_user' not in session:
        return redirect(url_for('index'))
    
    email = session['pending_2fa_user']
    user = MOCK_USERS.get(email, {})
    
    return render_template('2fa.html', 
                         phone=user.get('phone', ''),
                         backup_email=user.get('backup_email', ''))


@app.route('/send-2fa-code', methods=['POST'])
def send_2fa_code():
    """Send 2FA code (mock implementation)"""
    data = request.get_json()
    method = data.get('method', 'SMS')
    
    if 'pending_2fa_user' not in session:
        return jsonify({'success': False, 'message': 'No pending authentication'}), 400
    
    code = random.randint(100000, 999999)
    
    return jsonify({
        'success': True,
        'code': code,
        'method': method
    })


@app.route('/verify-2fa', methods=['POST'])
def verify_2fa():
    """Verify 2FA code"""
    if 'pending_2fa_user' not in session:
        return jsonify({'success': False, 'message': 'No pending authentication'}), 400
    
    data = request.get_json()
    code = data.get('code', '')
    
    session['user'] = session.pop('pending_2fa_user')
    
    return jsonify({'success': True})


@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('index'))


# ============================================================================
# DASHBOARD ROUTES (Protected)
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html', user_email=session.get('user'))


@app.route('/campaigns')
@login_required
def campaigns_page():
    """Campaigns management page"""
    return render_template('campaigns.html', user_email=session.get('user'))


@app.route('/segments')
@login_required
def segments_page():
    """Segments management page"""
    return render_template('segments.html', user_email=session.get('user'))


@app.route('/analytics')
@login_required
def analytics_page():
    """Analytics page"""
    return render_template('analytics.html', user_email=session.get('user'))


# ============================================================================
# API PROXY ROUTES (Protected - Proxy to Backend)
# ============================================================================

@app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def api_proxy(path):
    """Proxy API requests to backend (requires login)"""
    backend_url = f"{BACKEND_API_URL}/api/{path}"
    
    try:
        if request.method == 'GET':
            response = requests.get(backend_url, params=request.args)
        elif request.method == 'POST':
            response = requests.post(backend_url, json=request.get_json())
        elif request.method == 'PUT':
            response = requests.put(backend_url, json=request.get_json())
        elif request.method == 'DELETE':
            response = requests.delete(backend_url)
        
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Backend service unavailable', 'details': str(e)}), 503


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Marketing Automation Frontend'
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
