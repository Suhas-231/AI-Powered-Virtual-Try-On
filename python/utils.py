import os
import cv2
import requests
from flask import send_from_directory
from twilio.rest import Client as TwilloClient
from gradio_client import Client as GradioApp, file
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Twilio credentials
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Initialize Twilio WhatsApp client
twilio_client = TwilloClient(ACCOUNT_SID, AUTH_TOKEN)

# Initialize Gradio (Hugging Face) client for Virtual Try-On
# ✅ Using public model: HumanAIGC/OutfitAnyone
virtual_tryon_client = GradioApp("HumanAIGC/OutfitAnyone")


def send_result(phone_number, media_url):
    """
    Sends the result image of the virtual try-on back to the user via WhatsApp.
    """
    try:
        twilio_client.messages.create(
            body="✨ Your Virtual Try-On is Ready! ✨",
            media_url=[media_url],
            to=phone_number,
            from_='whatsapp:+14155238886',  # Twilio's WhatsApp number
        )
        print("✅ Result sent successfully to user!")
    except Exception as e:
        print(f"❌ Error sending result: {e}")


def perform_virtual_tryon(user_image_url, garment_image_url):
    """
    Performs the virtual try-on using the OutfitAnyone Hugging Face model.
    Downloads the user and garment images from Twilio,
    sends them to the model, and saves the result in 'static/result.png'.
    """
    # Step 1: Download both images from Twilio
    user_image_path = save_media(user_image_url, 'user_image.jpg')
    garment_image_path = save_media(garment_image_url, 'garment_image.jpg')

    if not user_image_path or not garment_image_path:
        print("❌ Failed to download one or both images from Twilio.")
        return None

    try:
        # Step 2: Call Hugging Face model
        print("🧠 Sending images to OutfitAnyone model on Hugging Face...")

        result = virtual_tryon_client.predict(
            file(user_image_path),    # Person image
            file(garment_image_path), # Garment image
            api_name="/tryon"         # ✅ Correct API endpoint for OutfitAnyone
        )

        # Step 3: Save output
        static_dir = 'static'
        os.makedirs(static_dir, exist_ok=True)
        output_path = os.path.join(static_dir, 'result.png')

        # If model returns URL (most common)
        if isinstance(result, str) and result.startswith("http"):
            response = requests.get(result)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print("✅ Try-on result image downloaded from Hugging Face.")
                return "/static/result.png"
            else:
                print("❌ Failed to fetch image from Hugging Face result URL.")
                return None

        # If model returns local path (less common)
        elif isinstance(result, str) and os.path.exists(result):
            img = cv2.imread(result)
            cv2.imwrite(output_path, img)
            print("✅ Try-on result image saved locally.")
            return "/static/result.png"

        else:
            print("⚠ Unexpected model output format.")
            return None

    except Exception as e:
        print(f"❌ Error during try-on process: {e}")
        return None


def save_media(media_url, file_name):
    """
    Downloads media sent via Twilio (person/garment image)
    and saves it locally.
    """
    try:
        message_sid = media_url.split('/')[-3]
        media_sid = media_url.split('/')[-1]

        media = twilio_client.api.accounts(ACCOUNT_SID).messages(message_sid).media(media_sid).fetch()
        media_uri = media.uri.replace('.json', '')
        image_url = f"https://api.twilio.com{media_uri}"

        response = requests.get(image_url, auth=(ACCOUNT_SID, AUTH_TOKEN))
        if response.status_code == 200:
            with open(file_name, 'wb') as file:
                file.write(response.content)
            print(f"✅ Saved media file: {file_name}")
            return file_name
        else:
            print("❌ Failed to download image from Twilio.")
            return None

    except Exception as e:
        print(f"❌ Error downloading media from Twilio: {e}")
        return None


def serve_static_file(filename):
    """
    Serves a static file (image) from the 'static' directory.
    """
    static_file_path = os.path.join('static', filename)
    if os.path.exists(static_file_path):
        return send_from_directory('static', filename, mimetype='image/png')
    else:
        print(f"⚠ File not found: {filename}")
        return "File not found", 404