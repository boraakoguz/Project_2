document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('errorMessage');
            
            errorDiv.textContent = '';
            errorDiv.classList.remove('show');
            
            if (!validateEmail(email)) {
                showError('Please enter a valid email address', errorDiv);
                return;
            }
            
            if (password.length < 3) {
                showError('Password is too short', errorDiv);
                return;
            }
            
            fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (data.requires_2fa) {
                        window.location.href = '/2fa';
                    } else {
                        window.location.href = '/dashboard';
                    }
                } else {
                    showError(data.message || 'Invalid email or password', errorDiv);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showError('An error occurred. Please try again.', errorDiv);
            });
        });
    }
});

function validateEmail(email) {
    const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return re.test(String(email).toLowerCase());
}

function showError(message, errorDiv) {
    errorDiv.textContent = message;
    errorDiv.classList.add('show');
}
