# utils.py

from django.http import JsonResponse
from django.conf import settings
from firebase_admin import credentials, initialize_app, messaging

def send_push_notification(fcm_token, title, body, data={}):
    if not fcm_token:
        return JsonResponse({'error': 'Missing fcm_token parameter'}, status=400)

    # Initialize Firebase Admin SDK
    # cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    # initialize_app(cred)

    firebase_app = settings.FIREBASE_APPS['push_notifications']

    # Send push notification
    message = messaging.Message(
        data=data,
        notification=messaging.Notification(title=title, body=body),
        token=fcm_token,
    )

    try:
        response = messaging.send(message,app=firebase_app)
        print("response", response)
    except Exception as e:
        print("error", e)
