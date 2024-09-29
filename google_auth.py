from firebase_config import db
from fastapi import HTTPException, Request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from firebase_admin import auth
import os
from dotenv import load_dotenv
from typing import Dict

load_dotenv()

user_tokens: Dict[str, Dict] = {
}

def user_token_update(user_id: str):
    global user_tokens
    user_tokens['user_id'] = user_id

    return user_tokens

flow = Flow.from_client_secrets_file(
    'client_secret.json',
    scopes=[
        
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks"
    ],
    redirect_uri="http://localhost:8000/oauth2callback"
)

def get_user_credentials(user_id: str):
    user_info = db.collection('users').document(user_id).get().to_dict()
    if user_info and 'refresh_token' in user_info and 'access_token' in user_info:
        return user_info
    else:
        raise HTTPException(status_code=401, detail="User not authenticated or missing credentials")

    
def refreshing_token(user_id: str):
    user_info = get_user_credentials(user_id)
    refresh_token = user_info['refresh_token']
    access_token = user_info['access_token']
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv('GOOGLE_CLIENT_ID'), # Get from .env
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET') # Get from .env
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())


        # Update the firestore
        user_ref = db.collection('users').document(user_id)
        user_ref.update({
            'access_token': creds.token,
            'expires_at': creds.expiry.isoformat()
        })
        return 'Token refreshed'
    elif not creds.expired and creds.refresh_token:
        return 'Token not expired and can be used'
    else:
        print("Token not refreshed")
        raise HTTPException(status_code=401, detail="User not authenticated")

def login_redirect(credentials: Credentials):
    user_info_service = build('oauth2', 'v2', credentials=credentials)
    user_info = user_info_service.userinfo().get().execute()
    email = user_info['email']

    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        user = auth.create_user(email=email)

    # Update or create user document in Firestore
    user_ref = db.collection('users').document(user.uid)
    user_data = {
        'email': email,
        'refresh_token': credentials.refresh_token,
        'access_token': credentials.token,
        'expires_at': credentials.expiry.isoformat()
    }
    user_ref.set(user_data, merge=True)

    # Store tokens in global dictionary
    user_token_update(user.uid)

    # Create a custom token for Firebase Authentication

    custom_token = auth.create_custom_token(user.uid)

    return user, custom_token



