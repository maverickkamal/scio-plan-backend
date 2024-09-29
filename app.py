from user_context import UserContext
import os
import json
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request, Header
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse  # Add JSONResponse here
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from utils.persona import PERSONA
from plan_tools import *
from google_auth import *
from firebase_admin import firestore
import warnings
from google.cloud.firestore_v1.base_query import FieldFilter

load_dotenv()



# Set up Gemini API key
try:
    genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
except KeyError:
    raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not found in environment variables.")

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")



# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://scio-planning.vercel.app"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Gemini Model Setup ---
tool_functions = [
    get_calendar_list,
    create_calendar_event,
    quick_add_event,
    get_calendar_events,
    delete_calendar_event,
    update_calendar_event,
    create_task,
    get_tasks,
    delete_task,
    update_task,
    clear_tasks,
    get_task_list,
    schedule_study_time,
    get_saved_schedule
]

model = genai.GenerativeModel(model_name='gemini-1.5-flash-002', tools=tool_functions)
chat = model.start_chat(enable_automatic_function_calling=True)

class UserInput(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    function_calls: list

@app.post("/chat")
async def chat_with_scio(message: str = Form(...), user_id: str = Form(...), files: list[UploadFile] = File(None)):
    
    print(user_id)
    print(message)
    try:
        UserContext.set_user_id(user_id)
        uploaded_files = []
        if files:
            for file in files:
                # Save the uploaded file temporarily
                temp_file_path = f"temp_{file.filename}"
                with open(temp_file_path, "wb") as buffer:
                    buffer.write(await file.read())
                # Upload the file to Gemini
                uploaded_file = genai.upload_file(temp_file_path)
                uploaded_files.append(uploaded_file)
                os.remove(temp_file_path)  # Clean up the temporary file
        # Prepare the message for Gemini
        if uploaded_files:
            message_args = []
            for i in range(len(uploaded_files)):
                message_args.append(uploaded_files[i])
            message_args.append(message)
            response = chat.send_message(message_args)
            uploaded_files.clear()
        else:
            print("no files")
            response = chat.send_message(message)
            print("response here")
        return JSONResponse(content={
            "content": response.text
        })
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)

@app.post("/get_schedule")
async def get_schedule():
    try:
        saved_schedule = get_saved_schedule()
        print(saved_schedule)
        formatted_schedule = []
        for session in saved_schedule:
            formatted_session = {
                "type": session['type'],
                "task": session['task'],
                "start": session['start'].isoformat(),
                "end": session['end'].isoformat()
            }
            formatted_schedule.append(formatted_session)
        return JSONResponse(content={"schedule": formatted_schedule})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def stream_response(response_text):
    chunk_size = 100  # Adjust this value as needed
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i+chunk_size]
        yield f"data: {json.dumps({'response': chunk})}\n\n"
    yield "data: [DONE]\n\n"

@app.get("/")
async def root():
    return {"message": "Welcome to Scio API"}

# You can add more routes here for specific functionalities if needed

@app.get("/login")
async def get_auth_url():
    authorization_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return {"url": authorization_url}

@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    # Ignore scope change warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=Warning)
        flow.fetch_token(code=request.query_params.get("code"))

    credentials = flow.credentials
    user, custom_token = login_redirect(credentials)
    
    # Redirect to the frontend's OAuth callback route with the tokens
    frontend_callback_url = "https://scio-planning.vercel.app/oauth-callback"
    redirect_url = f"{frontend_callback_url}?id_token={custom_token.decode()}&access_token={credentials.token}&user_id={user.uid}"
    return RedirectResponse(url=redirect_url)

@app.get("/chat_history/{user_id}")
async def get_chat_history(user_id: str):
    chat_history_ref = db.collection('chatHistory')
    query = chat_history_ref.where(filter=FieldFilter("userId", "==", user_id)).order_by("updatedAt", direction=firestore.Query.DESCENDING)
    
    docs = query.stream()
    chat_history = []
    for doc in docs:
        chat_data = doc.to_dict()
        chat_data['id'] = doc.id
        chat_history.append(chat_data)
    
    return {"chat_history": chat_history}

@app.post("/save_chat")
async def save_chat(chat_data: dict):
    chat_history_ref = db.collection('chatHistory')
    
    if 'id' in chat_data:
        # Update existing chat
        chat_ref = chat_history_ref.document(chat_data['id'])
        chat_ref.update(chat_data)
    else:
        # Create new chat
        chat_history_ref.add(chat_data)
    
    return {"message": "Chat saved successfully"}






if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
