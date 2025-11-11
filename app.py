import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Import helper functions from utils.py
from python.utils import send_result, perform_virtual_tryon, serve_static_file
#from python.llm_handler import handle_user_message  # Optional if you have a chatbot response system

# Load environment variables
load_dotenv()

# Initialize Flask
app = Flask(__name__)

# Global dictionary to track user sessions
session_data = {}

# Ngrok URL for serving static results (from .env)
NGROK_URL = os.getenv("NGROK_URL")


@app.route("/", methods=["POST"])
def process_request():
    """
    Handles all incoming WhatsApp messages from Twilio webhook.
    """
    sender = request.form.get("From")
    media_link = request.form.get("MediaUrl0")
    user_message = request.form.get("Body", "").strip().lower()

    # Twilio Messaging Response
    twilio_resp = MessagingResponse()

    # Initialize session for new user
    if sender not in session_data:
        session_data[sender] = {}

    # --- Case 1: When a user sends text message (no media) ---
    if user_message and not media_link:
        # If system is waiting for user input ("0" or "1" for image type)
        if "pending_media" in session_data[sender] and "expecting_response" in session_data[sender]:

            # User confirms uploaded image is a person
            if user_message == "0":
                session_data[sender]["user_image"] = session_data[sender]["pending_media"]
                twilio_resp.message("✅ Person image received! Now please send the garment image.")
                del session_data[sender]["pending_media"]
                del session_data[sender]["expecting_response"]

            # User confirms uploaded image is a garment
            elif user_message == "1":
                session_data[sender]["garment_image"] = session_data[sender]["pending_media"]
                twilio_resp.message("👕 Garment image received! Now please send the person image.")
                del session_data[sender]["pending_media"]
                del session_data[sender]["expecting_response"]

            # If both images are received, start the try-on process
            if "user_image" in session_data[sender] and "garment_image" in session_data[sender]:
                twilio_resp.message("🧠 Processing your virtual try-on... Please wait a moment ⏳")

                tryon_result_url = perform_virtual_tryon(
                    session_data[sender]["user_image"],
                    session_data[sender]["garment_image"]
                )

                if tryon_result_url:
                    result_url = f"{NGROK_URL}{tryon_result_url}"
                    send_result(sender, result_url)
                    twilio_resp.message("🎉✨ Your Virtual Try-On is Ready! ✨🎉")
                else:
                    twilio_resp.message("⚠ Sorry! Something went wrong during the try-on process.")

                # Clear session after completion
                del session_data[sender]

        else:
           twilio_resp.message("Please send your person image followed by garment image.")

    # --- Case 2: When user sends an image (media) ---
    elif media_link:
        session_data[sender]["pending_media"] = media_link
        session_data[sender]["expecting_response"] = True
        twilio_resp.message("📸 Got your image! Please reply with:\n👉 '0' for person image\n👉 '1' for garment image")

    # --- Case 3: Invalid input or unexpected condition ---
    else:
        twilio_resp.message("❓Please send a valid text or image message.")

    return str(twilio_resp)


@app.route("/static/<filename>")
def serve_image(filename):
    """
    Serves the processed result image (from /static directory).
    """
    return serve_static_file(filename)


if __name__ == "__main__":
    print("🚀 Starting Flask server for Virtual Try-On...")
    app.run(host="0.0.0.0", port=5000)