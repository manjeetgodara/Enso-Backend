#TODO: Sms service keys needs to be updated
import requests
from django.http import JsonResponse
def send_otp(mobile,otp):
    url=""
    api_key=""
    message=f"Your Enso OTP is: {otp}"

    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'apikey':api_key,
    }

    data = {
        'channel': 'sms',
        'source':"YOUR_SOURCE_NUMBER",
        'destination': mobile,
        'message':message,
    }

    response =requests.post(url,headers=headers,data=data)
    return response

def ResponseHandler(error, message, body, status_code):
    data = {
        "error": error,
        "message": message,
        "body": body,
    }
    return JsonResponse(data, status=status_code)

async def ResponseHandlerAsync(error, message, body, status_code):
    data = {
        "error": error,
        "message": message,
        "body": body,
    }
    return await JsonResponse(data, status=status_code)    