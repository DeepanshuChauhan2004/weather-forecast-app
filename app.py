import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- CONFIGURATION ---

# 1. Create the Flask App
app = Flask(__name__)

# 2. Set a secret key for security (required for sessions and login)
app.config['SECRET_KEY'] = 'a_very_secret_key_change_this_later'

# 3. Configure the database (SQLite)
# This creates a file named 'users.db' in your project folder
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 4. Initialize Database & Login Manager
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # The page to redirect to if user is not logged in

# 5. YOUR WEATHER API KEY
# !!! IMPORTANT: Replace this with your own key from OpenWeatherMap.org !!!
# After
OPENWEATHER_API_KEY = "YOUR_API_KEY"

# --- DATABASE MODEL ---

# This is the 'User' table in our database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # Method to set the password
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Method to check the password
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# This function is required by Flask-Login to load the current user
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- ROUTES (The App's Pages) ---

@app.route('/')
@login_required  # This protects the page! User must be logged in.
def index():
    """Shows the main weather search page."""
    # We will create 'index.html' next
    return render_template('index.html', username=current_user.username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles the login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index')) # If already logged in, go to index

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(password):
            login_user(user) # This logs them in
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger') # Show an error
            
    # For a GET request, just show the login page
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles the registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose another.', 'warning')
            return redirect(url_for('register'))
            
        # Create new user
        new_user = User(username=username)
        new_user.set_password(password)
        
        # Add to database
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
        
    # For a GET request, just show the registration page
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Logs the user out."""
    logout_user()
    return redirect(url_for('login'))

# --- API ROUTE (for fetching weather by City) ---

@app.route('/get_weather', methods=['POST'])
@login_required
def get_weather():
    """
    Called by JavaScript. Takes a city, gets BOTH current weather 
    and 5-day forecast, and returns them as a single JSON.
    """
    city = request.form['city']
    if not city:
        return jsonify({'error': 'City not provided'}), 400
        
    if OPENWEATHER_API_KEY == "YOUR_API_KEY_HERE":
         return jsonify({'error': 'Invalid API Key. Please check app.py'}), 500

    # URLs for the two API calls
    current_weather_url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    
    try:
        # --- First call: Get Current Weather ---
        current_response = requests.get(current_weather_url)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        if current_data.get('cod') != 200:
            return jsonify({'error': current_data.get('message', 'City not found')}), 404
        
        # --- Second call: Get 5-Day Forecast ---
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        if forecast_data.get('cod') != "200":
             return jsonify({'error': forecast_data.get('message', 'Forecast not found')}), 404

        # --- Combine them into one response ---
        combined_data = {
            'current': current_data,
            'forecast': forecast_data
        }
        
        return jsonify(combined_data)
        
    except requests.exceptions.HTTPError as errh:
        return jsonify({'error': f"HTTP Error: {errh}"}), 500
    except requests.exceptions.ConnectionError as errc:
        return jsonify({'error': f"Connection Error: {errc}"}), 500
    except requests.exceptions.Timeout as errt:
        return jsonify({'error': f"Timeout Error: {errt}"}), 500
    except requests.exceptions.RequestException as err:
        return jsonify({'error': f"An error occurred: {err}"}), 500

# --- API ROUTE (for fetching weather by Coords) ---

@app.route('/get_weather_by_coords', methods=['POST'])
@login_required
def get_weather_by_coords():
    """
    Called by JavaScript. Takes lat/lon, gets BOTH current weather 
    and 5-day forecast, and returns them as a single JSON.
    """
    lat = request.form['lat']
    lon = request.form['lon']
    
    if not lat or not lon:
        return jsonify({'error': 'Coordinates not provided'}), 400
        
    if OPENWEATHER_API_KEY == "YOUR_API_KEY_HERE":
         return jsonify({'error': 'Invalid API Key. Please check app.py'}), 500

    # URLs for the two API calls
    current_weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    
    try:
        # --- First call: Get Current Weather ---
        current_response = requests.get(current_weather_url)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        if current_data.get('cod') != 200:
            return jsonify({'error': current_data.get('message', 'City not found')}), 404
            
        # --- Second call: Get 5-Day Forecast ---
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        if forecast_data.get('cod') != "200":
             return jsonify({'error': forecast_data.get('message', 'Forecast not found')}), 404

        # --- Combine them into one response ---
        combined_data = {
            'current': current_data,
            'forecast': forecast_data
        }
        
        return jsonify(combined_data)
        
    except requests.exceptions.HTTPError as errh:
        return jsonify({'error': f"HTTP Error: {errh}"}), 500
    except requests.exceptions.ConnectionError as errc:
        return jsonify({'error': f"Connection Error: {errc}"}), 500
    except requests.exceptions.Timeout as errt:
        return jsonify({'error': f"Timeout Error: {errt}"}), 500
    except requests.exceptions.RequestException as err:
        return jsonify({'error': f"An error occurred: {err}"}), 500

# --- RUN THE APP ---

if __name__ == '__main__':
    # This creates the database file (users.db) if it doesn't exist
    with app.app_context():
        db.create_all()
    
    # Starts the web server
    # debug=True means it will auto-reload when you save changes
    app.run(debug=True)