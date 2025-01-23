from flask import Flask, render_template, request, flash, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo
from flask_sqlalchemy import SQLAlchemy
import fitz  # PyMuPDF
import difflib
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model for the database
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

# Create the database and tables
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid email or password', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if the email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'error')
            return redirect(url_for('register'))

        # Create a new user
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(email=form.email.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        try:
            # Check if files are uploaded
            if 'file1' not in request.files or 'file2' not in request.files:
                flash('Please upload both files!', 'error')
                return render_template('index.html')

            file1 = request.files['file1']
            file2 = request.files['file2']

            # Check if files are empty
            if file1.filename == '' or file2.filename == '':
                flash('Please upload valid files!', 'error')
                return render_template('index.html')

            # Save files to the upload folder
            file1_path = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename)
            file2_path = os.path.join(app.config['UPLOAD_FOLDER'], file2.filename)
            file1.save(file1_path)
            file2.save(file2_path)

            # Extract text from PDFs
            text1 = extract_text_from_pdf(file1_path)
            text2 = extract_text_from_pdf(file2_path)

            # Check if text extraction was successful
            if text1 is None or text2 is None:
                flash('Error extracting text from PDFs. Please check the files.', 'error')
                return render_template('index.html')

            # Compare texts
            differences = compare_texts(text1, text2, file1.filename, file2.filename)

            # Delete the files after comparison
            try:
                os.remove(file1_path)
                os.remove(file2_path)
            except Exception as e:
                print(f"Error deleting files: {e}")

            # Render the result
            if differences is None:
                return render_template('index.html', identical=True)
            else:
                return render_template('index.html', differences=differences)

        except Exception as e:
            # Log the error and display a user-friendly message
            print(f"Internal Server Error: {e}")
            flash('An internal error occurred. Please try again.', 'error')
            return render_template('index.html')

    return render_template('index.html')

# Helper functions
def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

def normalize_text(text):
    """Normalize text by removing extra spaces and newlines."""
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def compare_texts(text1, text2, file1_name, file2_name):
    """Compare two texts and return the exact differences with file names."""
    try:
        # Normalize the texts
        text1 = normalize_text(text1)
        text2 = normalize_text(text2)

        # Check if texts are identical
        if text1 == text2:
            return None

        # Split the texts into words for a more accurate comparison
        diff = difflib.ndiff(text1.split(), text2.split())

        # Collect differences
        differences = []
        for line in diff:
            if line.startswith('+ '):
                # Difference from file2 (added content)
                differences.append(f"{file2_name}: {line}")
            elif line.startswith('- '):
                # Difference from file1 (removed content)
                differences.append(f"{file1_name}: {line}")

        return differences
    except Exception as e:
        print(f"Error comparing texts: {e}")
        return None

# Ensure the upload folder exists
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if __name__ == '__main__':
    app.run(debug=True)  # Set debug=True for development