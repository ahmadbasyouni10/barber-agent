from flask import Flask, request, Response, session
from dotenv import load_dotenv
import os
import secrets
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from flask import render_template_string
import atexit
from datetime import datetime

# Import our custom agent
from chains.agent import process_incoming_message
from services.notification_service import send_sms, schedule_reminders, get_scheduled_reminders

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Required for session

# Initialize scheduler for reminders
scheduler = BackgroundScheduler()
scheduler.start()

# Register shutdown function to properly clean up scheduler
atexit.register(lambda: scheduler.shutdown())

@app.route('/sms', methods=['POST'])
def incoming_sms():
    """Handle incoming SMS messages from Twilio webhook"""
    # Get the message content and sender's phone number
    incoming_message = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    logger.info(f"Received SMS from {sender}: {incoming_message}")
    
    # Process the message using our LangChain agent
    agent_response = process_incoming_message(sender, incoming_message)
    
    # Initialize Twilio response
    response = MessagingResponse()
    response.message(agent_response)
    
    return str(response)

@app.route('/')
def index():
    """Simple home page with info about the app"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Barber Agent</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .card { background: #f9f9f9; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
            a { display: inline-block; background: #4CAF50; color: white; padding: 10px 15px; 
                text-decoration: none; border-radius: 4px; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>Barber Scheduling Agent</h1>
        <div class="card">
            <h2>Welcome!</h2>
            <p>This is a simple AI-powered scheduling agent for a barber shop.</p>
            <p>Use the web interface below to test the agent without using SMS.</p>
            <a href="/chat">Open Web Chat</a>
        </div>
    </body>
    </html>
    """)

@app.route('/chat', methods=['GET', 'POST'])
def web_chat():
    """Provide a simple web interface to test the agent without SMS"""
    message_history = []
    
    if request.method == 'POST':
        user_message = request.form.get('message', '').strip()
        user_phone = request.form.get('phone', '+12345678901')  # Default test phone
        
        if user_message:
            try:
                # Process the message with our agent
                agent_response = process_incoming_message(user_phone, user_message)
                # Add to session history for display
                if 'history' not in session:
                    session['history'] = []
                session['history'].append({
                    'user': user_message,
                    'agent': agent_response,
                    'time': datetime.now().strftime("%H:%M:%S")
                })
                message_history = session['history']
            except Exception as e:
                logger.error(f"Error in web chat: {e}")
                message_history = session.get('history', [])
                message_history.append({
                    'user': user_message,
                    'agent': f"Sorry, I encountered an error: {str(e)}",
                    'time': datetime.now().strftime("%H:%M:%S")
                })
        else:
            message_history = session.get('history', [])
    else:
        # Clear history on GET request
        session['history'] = []
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Barber Agent - Web Chat</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #333; }
            .chat { background: #f9f9f9; border-radius: 8px; padding: 20px; margin-bottom: 20px; height: 400px; overflow-y: auto; }
            .message { margin-bottom: 15px; }
            .user { text-align: right; }
            .user .bubble { background: #4CAF50; color: white; border-radius: 18px 18px 0 18px; }
            .agent .bubble { background: #e9e9e9; border-radius: 18px 18px 18px 0; }
            .bubble { display: inline-block; padding: 10px 15px; max-width: 70%; word-wrap: break-word; }
            .time { font-size: 12px; color: #888; margin: 5px 0; }
            .input-form { display: flex; }
            .input-form input { flex-grow: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px 0 0 4px; }
            .input-form button { background: #4CAF50; color: white; border: none; padding: 10px 15px; border-radius: 0 4px 4px 0; cursor: pointer; }
            .phone-input { width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; }
            .home-link { display: inline-block; margin-bottom: 20px; color: #4CAF50; text-decoration: none; }
            .home-link:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <a href="/" class="home-link">← Back to Home</a>
        <h1>Chat with Barber Agent</h1>
        <div id="chat" class="chat">
            {% for message in message_history %}
                <div class="message user">
                    <div class="bubble">{{ message.user }}</div>
                    <div class="time">{{ message.time }}</div>
                </div>
                <div class="message agent">
                    <div class="bubble">{{ message.agent }}</div>
                    <div class="time">{{ message.time }}</div>
                </div>
            {% endfor %}
        </div>
        
        <form method="post">
            <input type="text" name="phone" class="phone-input" placeholder="Your phone number (e.g. +12345678901)" value="{{ request.form.get('phone', '+12345678901') }}">
            <div class="input-form">
                <input type="text" name="message" placeholder="Type your message here..." autofocus>
                <button type="submit">Send</button>
            </div>
        </form>
        
        <script>
            // Auto-scroll to bottom of chat
            var chatDiv = document.getElementById("chat");
            chatDiv.scrollTop = chatDiv.scrollHeight;
        </script>
    </body>
    </html>
    """, message_history=message_history)

@app.route('/status', methods=['GET'])
def status():
    """Show the status of the application and scheduled reminders"""
    reminders = get_scheduled_reminders()
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Barber Agent Status</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1, h2 { color: #333; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            .home-link { display: inline-block; margin-bottom: 20px; color: #4CAF50; text-decoration: none; }
            .home-link:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <a href="/" class="home-link">← Back to Home</a>
        <h1>Barber Agent Status</h1>
        
        <div>
            <h2>Application Status</h2>
            <p>Server is running normally.</p>
            <p>Services available:</p>
            <ul>
                <li>SMS Handling (/sms endpoint)</li>
                <li>Web Chat Interface (/chat endpoint)</li>
            </ul>
        </div>
        
        <div>
            <h2>Scheduled Reminders</h2>
            {% if reminders %}
                <table>
                    <tr>
                        <th>Phone Number</th>
                        <th>Message</th>
                        <th>Scheduled Time</th>
                    </tr>
                    {% for reminder in reminders %}
                    <tr>
                        <td>{{ reminder.phone }}</td>
                        <td>{{ reminder.message }}</td>
                        <td>{{ reminder.run_time }}</td>
                    </tr>
                    {% endfor %}
                </table>
            {% else %}
                <p>No reminders currently scheduled.</p>
            {% endif %}
        </div>
    </body>
    </html>
    """, reminders=reminders)

if __name__ == "__main__":
    # Schedule reminders for any upcoming appointments
    schedule_reminders(scheduler)
    
    # Get PORT from environment variable or use default
    port = int(os.environ.get("PORT", 5000))
    
    # Print a message to show available routes
    public_url = os.environ.get("PUBLIC_URL", f"http://localhost:{port}")
    logger.info(f"Server starting up...")
    logger.info(f"SMS webhook URL: {public_url}/sms")
    logger.info(f"Web interface available at: {public_url}")
    logger.info(f"Status page: {public_url}/status")
    
    # Start the Flask app
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true") 