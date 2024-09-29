import firebase_admin
from firebase_admin import credentials, auth, firestore


# Initialize Firebase
cred = credentials.Certificate("/etc/secrets/serviceAccountKey.json")
firebase_app = firebase_admin.initialize_app(cred)

db = firestore.client()

