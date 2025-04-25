# Barber Appointment Agent

An AI-powered scheduling assistant for barber shops, built with LangChain and OpenAI.

## Features

- Book haircut appointments with natural language
- Check barber availability
- Cancel or reschedule appointments
- Reminder notifications for upcoming appointments
- Multi-channel: Supports SMS, Telegram, and web interface
- Google Sheets integration for appointment storage

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your credentials (use `.env.example` as a template)
4. Set up your integrations:
   - Twilio for SMS (optional)
   - Telegram bot (optional)
   - Google Sheets for appointment storage

## Running the Agent

This system can be run in multiple ways, depending on which interface you want to use.

### Option 1: Telegram Bot (Recommended for Testing)

The easiest way to test the system is with the Telegram bot in polling mode:

1. Make sure you have set up a bot with BotFather and added the token to your `.env` file:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   BARBER_TELEGRAM_ID=your_telegram_id_here  # This is where notifications will be sent
   ```

2. Run the bot in polling mode:
   ```
   python run_telegram.py
   ```

3. Send a message to your bot in Telegram

This method is the most reliable for testing and doesn't require ngrok or a public URL.

### Option 2: Web Chat Interface

To use the web chat interface:

1. Start the Flask server:
   ```
   python app.py
   ```

2. Open `http://localhost:5000` in your browser
3. Click on "Open Web Chat" to test the agent

### Option 3: SMS with Twilio

To receive SMS messages:

1. Start ngrok to create a tunnel:
   ```
   python ngrok_tunnel.py
   ```

2. Start the Flask server in another terminal:
   ```
   python app.py
   ```

3. Configure your Twilio phone number to use the ngrok webhook URL for SMS
   (see [Twilio setup instructions](./docs/twilio_setup.md) for more details)

## Configuration

### Required Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key
- `GOOGLE_SHEET_ID`: The ID of your Google Sheet for storing appointments
- `GOOGLE_SHEETS_CREDENTIALS_FILE`: Path to your Google Sheets service account credentials

### Optional Environment Variables

- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: For SMS functionality
- `TELEGRAM_BOT_TOKEN`, `BARBER_TELEGRAM_ID`: For Telegram functionality
- `LANGSMITH_API_KEY`: For debugging agent behavior with LangSmith (optional)

## Testing

You can test the agent without setting up integrations:

```
python test_agent.py
```

This will let you interact with the agent via command line.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for solutions to common issues.

## License

MIT 