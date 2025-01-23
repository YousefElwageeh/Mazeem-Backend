"""
API for the Mazeem project - a service to facilitate sending event invitations via WhatsApp.

The API includes:
1. User Authentication
2. Sending Invitations
3. Accepting or Rejecting Invitations
4. Viewing Sent Invitations
5. Viewing Accepted Invitations
6. Viewing Rejected Invitations
7. Generating QR Codes for Invitations
8. Verifying Invitations via QR Codes
"""

from flask import Flask, request, jsonify, Blueprint , render_template, send_from_directory , redirect , flash , session , url_for , send_file , make_response , Response 
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from flask_sqlalchemy import SQLAlchemy
from models.sendbox import sendbox
from flask_migrate import Migrate
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import datetime
import time
import os
import random
import string
import requests
# import twillo to send a message in whatsapp
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
# import lib for genrating qrcode
import segno
from time import sleep

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.secret_key = 'mazeem@2090'
app.config.update(
    SQLALCHEMY_DATABASE_URI='sqlite:///mazeem.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER='static/uploads',
    ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg', 'gif'},
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    JWT_SECRET='mazeem@2090',
    JWT_ACCESS_TOKEN_EXPIRES=datetime.timedelta(days=90),
    APP_NAME='Mazeem',
    APP_VERSION='1.0.0',
    DEBUG=True,
    APP_URL='https://mazeem.abdelrahman-nasr.tech'
)

# make session saved 90 days
app.permanent_session_lifetime = datetime.timedelta(days=90)


# Setup Swagger UI
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger/swagger.yml'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Mazeem API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# Helper Functions
def save_image(file):
    if file:
        filename = file.filename
        new_filename = ''.join(random.choices(string.ascii_letters + string.digits, k=16)) + filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
        return new_filename
    return None

def send_invitation(event_id, phone):
    event = Events.query.get(event_id)
    if event:
        qrcode = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        message = f"""*{event.title}*\n--------------\n
        {event.description}\n---------------\n
        {event.location}
        \n---------لقبول الدعوة اضغط على الرابط التالي---------\n
        {app.config['APP_URL']}/eventset/accept/{qrcode}
        \n---------لرفض الدعوة اضغط على الرابط التالي---------\n
        {app.config['APP_URL']}/eventset/reject/{qrcode}
        """
        send_message_v(message, phone, file_url=f"{app.config['APP_URL']}/storage/{event.image}")
        invitation = Invitation(event_id=event_id, qrcode=qrcode, phone=phone, status='sent')
        db.session.add(invitation)
        db.session.commit()
    return False
def send_invitation_twilio(event_id, phone):
    invitation_message_template_sid = "HX1b3bfd25f38caf9f8374344ed7cce7bb"
    accept_invitation_button_sid = "HX1b3a4e096efadc4bc31f7c73c2b52afc"
    reject_invitation_button_sid = "HXbe0229ad617cf8f3c34fa9c75db609a7"
    event = Events.query.get(event_id)
    if event:
        qrcode = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        message = f"""*{event.title}*\n--------------\n
        {event.description}\n---------------\n
        {event.location}
        """
        sendbox(phone, {"1": message, "2": f"{event.image}"}, content_sid=invitation_message_template_sid)
        time.sleep(1)  # Wait for 1 second before sending the next message
        sendbox(phone, {"1": f"{qrcode}"}, content_sid=accept_invitation_button_sid)
        time.sleep(1)  # Wait for 1 second before sending the next message
        sendbox(phone, {"1": f"{qrcode}"}, content_sid=reject_invitation_button_sid)
        invitation = Invitation(event_id=event_id, qrcode=qrcode, phone=phone, status='sent')
        db.session.add(invitation)
        db.session.commit()
        return True
    return False

def send_message_v(message, to, appkey='c32fcdfc-d4de-4a91-9245-73c5f60a8dfb', authkey='KlQNL39BVlWOOwczuaU6fftagMgZ5LXx3QTI8GBEtOVWVysfk1', file_url=None):
    url = "https://api.appsenders.com/api/create-message"
    payload = {
        'appkey': 'c32fcdfc-d4de-4a91-9245-73c5f60a8dfb-',
        'authkey': 'KlQNL39BVlWOOwczuaU6fftagMgZ5LXx3QTI8GBEtOVWVysfk1',
        'to': to,
        'message': message
    }
    if file_url:
        payload['file'] = "https://i.pinimg.com/736x/25/98/2c/25982c2af2cca84c831a37dedfd15c66.jpg"
    headers = {}
    files = []
    response = requests.post(url, headers=headers, data=payload, files=files)
    return response.text

def qr_code_generator(invitation_id):
    invitation = Invitation.query.get(invitation_id)
    if invitation:
        qr = segno.make(invitation.qrcode)
        qr.save(f"static/uplodes/{invitation.qrcode}.png")
        return True
    return False
# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    image = db.Column(db.String(100), nullable=False)
    login_by = db.Column(db.String(100), nullable=False)  # form, google, facebook
    plan = db.Column(db.String(100), default='free')  
    send_message = db.Column(db.Integer, default=0)
    remaining_message = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Events(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=True, default=None)
    image = db.Column(db.String(100), nullable=True, default=None)
    date = db.Column(db.String(100), nullable=True, default=None)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    qrcode = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(100), nullable=False)  # sent, accept, reject
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class QRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    is_scanned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message_count = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    plan = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
class Plans(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    message_count = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# Blueprints
auth_bp = Blueprint('auth', __name__)
api_bp = Blueprint('api', __name__)
admin_bp = Blueprint('admin', __name__)
# Auth Routes

@app.route('/')
def home():
    return render_template('index.html')
@auth_bp.route('/login', methods=['POST'])
def login():
    identifier = request.json.get('identifier')
    password = request.json.get('password')

    user = User.query.filter((User.email == identifier) | (User.phone == identifier)).first()
    if user and user.password == password:
        access_token = create_access_token(identity=user.id)
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'access_token': access_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': user.phone,
                'name': user.name,
                'image': user.image,
                'remaining_message': user.remaining_message,
                'send_message': user.send_message,
                'plan': user.plan,
                'login_by': user.login_by,
                'plan': user.plan,
                'created_at': user.created_at
            }
        }), 200
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 400
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone')
    name = data.get('name')

    if not all([email, password, phone, name]):
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    if User.query.filter((User.email == email) | (User.phone == phone)).first():
        return jsonify({'status': 'error', 'message': 'User already exists'}), 400

    image = f'https://ui-avatars.com/api/?name={name}&size=256'
    user = User(email=email, password=password, phone=phone, name=name, image=image, login_by='form', plan='free', remaining_message=0, send_message=0)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    return jsonify({
        'status': 'success',
        'message': 'Registration successful',
        'access_token': access_token,
        'user': {
            'id': user.id,
            'email': user.email,
            'phone': user.phone,
            'name': user.name,
            'image': user.image,
            'login_by': user.login_by,
            'plan': user.plan,
            'created_at': user.created_at,
            'remaining_message': user.remaining_message,
            'send_message': user.send_message
        }
    }), 200

@auth_bp.route('/google-login', methods=['POST'])
def google_login():
    data = request.json
    email = data.get('email')
    user_id = data.get('user_id')
    name = data.get('name')

    if not all([email, user_id, name]):
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    if User.query.filter(User.email == email).first():
        user = User.query.filter(User.email == email).first()
        access_token = create_access_token(identity=user.id)
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'access_token': access_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': user.phone,
                'name': user.name,
                'image': user.image,
                'login_by': user.login_by,
                'plan': user.plan,
                'created_at': user.created_at,
                'remaining_message': user.remaining_message,
                'send_message': user.send_message
            }
        }), 200
    else:
        image = f'https://ui-avatars.com/api/?name={name}&size=256'
        user = User(email=email, password=user_id, phone=user_id, name=name, image=image, login_by='google', plan='free', remaining_message=0, send_message=0)
        db.session.add(user)
        db.session.commit()

        access_token = create_access_token(identity=user.id)
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'access_token': access_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': user.phone,
                'name': user.name,
                'image': user.image,
                'login_by': user.login_by,
                'plan': user.plan,
                'created_at': user.created_at,
                'remaining_message': user.remaining_message,
                'send_message': user.send_message
            }
        }), 200
@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    identifier = request.json.get('identifier')

    user = User.query.filter((User.email == identifier) | (User.phone == identifier)).first()
    if user:
        message = f"Your password is: {user.password}"
        # Assuming `sendbox` works as expected
        sendbox(user.phone, {"1": message}, content_sid="HX648ba0e24a5c72e0ae05e7f8bd68f793")
        return jsonify({'status': 'success', 'message': 'Password sent'}), 200
    return jsonify({'status': 'error', 'message': 'User not found'}), 404
@auth_bp.route('/profile', methods=['GET', 'POST'])
@jwt_required()
def profile():
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404

        if request.method == 'POST':
            # Handle form data
            email = request.form.get('email')
            phone = request.form.get('phone')
            name = request.form.get('name')
            image = request.files.get('image')
            
            # Update user details
            if email:
                user.email = email
            if phone:
                user.phone = phone
            if name:
                user.name = name
            if image:
                # Save the image file
                user.image = save_image(image)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success', 
                'message': 'Profile updated',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'phone': user.phone,
                    'name': user.name,
                    'image': f'{request.host_url}storage/{user.image}',
                    'login_by': user.login_by,
                    'plan': user.plan,
                    'created_at': user.created_at,
                    'remaining_message': user.remaining_message,
                    'send_message': user.send_message
                }
            }), 200

        # Handle GET request
        events = Events.query.filter_by(user_id=user.id).all()
        subscriptions = Subscription.query.filter_by(user_id=user.id).all()
        if user.image and not user.image.startswith('http'):
            user.image = f"{request.host_url}storage/{user.image}"
        return jsonify({
            'status': 'success',
            'message': 'Profile data',
            'user': {
                'id': user.id,
                'email': user.email,
                'phone': user.phone,
                'name': user.name,
                'image': user.image,
                'login_by': user.login_by,
                'remaining_message': user.remaining_message,
                'send_message': user.send_message,
                'plan': user.plan,
                'created_at': user.created_at
            },
            'events': [
                {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'location': event.location,
                    'image': f"{request.host_url}storage/{event.image}",
                    'date': event.date,
                    'created_at': event.created_at
                } for event in events
            ],
            'subscriptions': [
                {
                    'id': subscription.id,
                    'message_count': subscription.message_count,
                    'price': subscription.price,
                    'plan': subscription.plan,
                    'created_at': subscription.created_at
                } for subscription in subscriptions
            ]
        }), 200
# event management
@api_bp.route('/create-event', methods=['POST'])
@jwt_required()
def create_event():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)  # Fetch the user object

    # Check if the request has form data or JSON
    if 'multipart/form-data' in request.content_type:
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        date = request.form.get('date')
        image = request.files.get('image')

        if not all([title, description, date]):
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400

        # Handle image save
        image_filename = save_image(image)

    else:  # Handle JSON body
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        location = data.get('location')
        date = data.get('date')

        if not all([title, description, date]):
            return jsonify({'status': 'error', 'message': 'Missing data'}), 400

        image_filename = None  # JSON request won't include an image

    # Create the event
    event = Events(user_id=user_id, title=title, description=description, location=location, image=image_filename, date=date)
    db.session.add(event)
    db.session.commit()

    # Send invitations (optional feature)
    all_phones = request.form.get('phone_numbers')
    if all_phones:
        phone_numbers = all_phones.split(',')
        phone_number_count = len(phone_numbers)
        
        # Ensure user.remaining_message is not None
        if user.remaining_message is None:
            return jsonify({'status': 'error', 'message': 'User has no message credits available'}), 400
        
        if phone_number_count > user.remaining_message:
            return jsonify({'status': 'error', 'message': 'Insufficient message credits'}), 400
        
        user.remaining_message -= phone_number_count
        user.send_message += phone_number_count

        db.session.commit()
        for phone in phone_numbers:
            # send message with twilio
            send_invitation_twilio(event.id, phone)

    response = {
        'status': 'success',
        'message': 'Event created',
        'event': {
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'location': event.location,
            'image': f"{request.host_url}storage/{event.image}",
            'date': event.date,
            'created_at': event.created_at
        }
    }
    return jsonify(response), 201

@api_bp.route('/edit-event/<int:event_id>', methods=['POST'])
@jwt_required()
def edit_event(event_id):
    user_id = get_jwt_identity()
    event = Events.query.get(event_id)
    if not event:
        return jsonify({'status': 'error', 'message': 'Event not found'}), 404

    if event.user_id != user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    title = request.json.get('title')
    description = request.json.get('description')
    location = request.json.get('location')
    image = request.files.get('image')

    if title:
        event.title = title
    if description:
        event.description = description
    if location:
        event.location = location
    if image:
        image_filename = save_image(image)
        event.image = image_filename

    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Event updated'}), 200
@api_bp.route('/delete-event/<int:event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    user_id = get_jwt_identity()
    event = Events.query.get(event_id)
    if not event:
        return jsonify({'status': 'error', 'message': 'Event not found'}), 404

    if event.user_id != user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    db.session.delete(event)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Event deleted'}), 200
@app.route('/api/list-events', methods=['GET'])
@jwt_required()
def list_events():
    try:
        user_id = get_jwt_identity()  # Get the current user's ID from JWT
        events = Events.query.filter_by(user_id=user_id).all()  # Get all events created by the user

        if not events:
            return jsonify({'status': 'error', 'message': 'No events found'}), 404

        event_list = []
        for event in events:
            # Fetch invitations related to the event
            invitations = Invitation.query.filter_by(event_id=event.id).all()
            invitation_list = [
                {
                    'invitation_id': invitation.id,
                    'qrcode': invitation.qrcode,
                    'phone': invitation.phone,
                    'status': invitation.status,
                    'created_at': invitation.created_at.strftime('%Y-%m-%d %H:%M:%S')
                } for invitation in invitations
            ]
            accept_count = len([i for i in invitation_list if i['status'] == 'accept'])
            reject_count = len([i for i in invitation_list if i['status'] == 'reject'])
            send_count = len([i for i in invitation_list if i['status'] == 'sent'])
            # Prepare event details
            event_data = {
                'event_id': event.id,
                'title': event.title,
                'description': event.description,
                'location': event.location,
                'image': f"{request.host_url}storage/{event.image}",
                'date': event.date,
                'accept_count': accept_count,
                'reject_count': reject_count,
                'send_count': send_count,
                'created_at': event.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'invitations': invitation_list
            }
            event_list.append(event_data)

        return jsonify({'status': 'success', 'events': event_list}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': 'An error occurred', 'details': str(e)}), 500

@api_bp.route('/event/<int:event_id>', methods=['GET'])
@jwt_required()
def get_event(event_id):
    user_id = get_jwt_identity()
    event = Events.query.get(event_id)
    if not event:
        return jsonify({'status': 'error', 'message': 'Event not found'}), 404

    if event.user_id != user_id:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    event.image = f"{request.host_url}storage/{event.image}"
    return jsonify({
        'status': 'success',
        'message': 'Event data',
        'event': {
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'location': event.location,
            'image': event.image,
            'date': event.date,
            'created_at': event.created_at
        }
    }), 200

@api_bp.route('/send-all-invitations', methods=['POST'])
@jwt_required()
def send_all_invitations():
    user_id = get_jwt_identity()
    event = request.json.get('event')
    phone_numbers = request.json.get('phone_numbers')
    
    if not phone_numbers:
        return jsonify({'status': 'error', 'message': 'Phone numbers are required'}), 400
    
    phone_number_count = len(phone_numbers)
    user = User.query.get(user_id)
    
    if not event:
        return jsonify({'status': 'error', 'message': 'Missing event data'}), 400
    
    # Check if remaining_message is None and handle it
    if user.remaining_message is None:
        return jsonify({'status': 'error', 'message': 'User has no message credits available'}), 400

    # Check if user has enough remaining message credits
    if phone_number_count > int(user.remaining_message):
        return jsonify({'status': 'error', 'message': 'Insufficient message credits'}), 400

    # Deduct message credits
    user.remaining_message -= phone_number_count
    user.send_message += phone_number_count
    db.session.commit()

    for phone in phone_numbers:
        # send message with twilio
        send_invitation_twilio(event, phone)
    return jsonify({'status': 'success', 'message': 'Invitations sent'}), 200

@api_bp.route('/validate-qr-code', methods=['POST'])
def validate_qr_code():
    qrcode = request.json.get('qrcode')
    invitation = Invitation.query.filter_by(qrcode=qrcode).first()
    if invitation:
        event = Events.query.get(invitation.event_id)
        if invitation.status == 'reject':
            return jsonify({'status': 'error', 'message': 'Invitation rejected'}), 400
        response = {
            'status': 'success',
            'message': 'QR Code validated',
            'invitation': {
                'id': invitation.id,
                'event': {
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'location': event.location,
                    'date': event.date,
                    'image': f"{request.host_url}storage/{event.image}"
                },
                'phone': invitation.phone,
                'status': invitation.status,
                'created_at': invitation.created_at
            }
        }
        return jsonify(response), 200
    return jsonify({'status': 'error', 'message': 'Invalid QR Code'}), 400

# subscription management
@api_bp.route('/subscribe', methods=['POST'])
@jwt_required()
def subscribe():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    plan_id = request.json.get('plan')
    if not plan_id:
        return jsonify({'status': 'error', 'message': 'Missing plan'}), 400

    plan = Plans.query.get(plan_id)
    if not plan:
        return jsonify({'status': 'error', 'message': 'Invalid plan'}), 400

    user.plan = plan.name
    user.remaining_message += plan.message_count
    db.session.commit()

    subscription = Subscription(user_id=user.id, message_count=plan.message_count, price=plan.price, plan=plan.name)
    db.session.add(subscription)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Subscribed'}), 201
@api_bp.route('/plans', methods=['GET'])
def plans():
    plans = Plans.query.all()
    plan_list = [
        {
            'id': plan.id,
            'name': plan.name,
            'message_count': plan.message_count,
            'price': plan.price,
        } for plan in plans
    ]
    return jsonify({'status': 'success', 'plans': plan_list}), 200

@api_bp.route('/subscriptions', methods=['GET'])
@jwt_required()
def subscriptions():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    subscriptions = Subscription.query.filter_by(user_id=user.id).all()
    subscription_list = [
        {
            'id': subscription.id,
            'message_count': subscription.message_count,
            'price': subscription.price,
            'plan': subscription.plan,
            'created_at': subscription.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for subscription in subscriptions
    ]
    return jsonify({'status': 'success', 'subscriptions': subscription_list}), 200
@api_bp.route('/delete-account', methods=['DELETE'])
@jwt_required()
def delete_account():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Account deleted'}), 200

@app.route('/eventset/accept/<qr_code>', methods=['GET'])
def accept_event(qr_code):
    invitation = Invitation.query.filter_by(qrcode=qr_code).first()
    event = Events.query.get(invitation.event_id)
    if invitation:
        if invitation.status == 'accept':
            return render_template('accept.html', message='Invitation already accepted', invitation=invitation, event=event)
        else:
            invitation.status = 'accept'
            db.session.commit()
            send_message_v(f"تم قبول الدعوة لحضور {event.title}", invitation.phone, file_url=f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={qr_code}.png")
            return render_template('accept.html', invitation=invitation, event=event)
        return render_template('accept.html', message='Invalid QR Code')


@app.route('/eventset/reject/<qr_code>', methods=['GET'])
def reject_event(qr_code):
    invitation = Invitation.query.filter_by(qrcode=qr_code).first()
    event = Events.query.get(invitation.event_id)
    if invitation:
        invitation.status = 'reject'
        db.session.commit()
        return render_template('reject.html', invitation=invitation, event=event)
    return render_template('reject.html', message='Invalid QR Code')


@app.route('/storage/<path:filename>')
def storage(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



# admin routes
@admin_bp.route('/login', methods=['POST', 'GET'])
def admin_login():
    if request.method == 'GET':
        if 'admin' in session:
            return redirect('/admin/dashboard')
        return render_template('admin/login.html')
    
    if request.method == 'POST':
        # Use request.form.get() for form data
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check credentials
        if email == 'admin@mazeem.com' and password == 'Mazeem@2090':
            session['admin'] = True
            session['email'] = email
            session.permanent = True
            flash('تم تسجيل الدخول بنجاح', 'success')
            return redirect('/admin/dashboard')
        
        # If credentials are wrong
        flash('خطأ في البريد الإلكتروني أو كلمة المرور', 'error')
        return redirect('/admin/login')
@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin', None)
    session.pop('email', None)
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect('/admin/login')

@admin_bp.route('/dashboard')
def admin_dashboard():
    if 'admin' in session:
        user_count = User.query.count()
        event_count = Events.query.count()
        invitation_count = Invitation.query.count()
        subscription_count = Subscription.query.count()
        last_25_users = User.query.order_by(User.created_at.desc()).limit(25).all()
        return render_template('admin/dashboard.html', user_count=user_count, event_count=event_count, invitation_count=invitation_count, subscription_count=subscription_count, last_25_users=last_25_users)
    return redirect('/admin/login')
@admin_bp.route('/users')
def admin_users():
    if 'admin' in session:
        users = User.query.all()
        return render_template('admin/users.html', users=users)
    return redirect('/admin/login')
@admin_bp.route('/events')
def admin_events():
    if 'admin' in session:
        events = Events.query.all()
        return render_template('admin/events.html', events=events)
    return redirect('/admin/login')
@admin_bp.route('/subscriptions')
def admin_subscriptions():
    if 'admin' in session:
        subscriptions = Subscription.query.all()
        return render_template('admin/subscriptions.html', subscriptions=subscriptions)
    return redirect('/admin/login')

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/admin')
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=9200)
