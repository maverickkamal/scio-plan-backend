from user_context import UserContext
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from google_auth import *
from google.oauth2.credentials import Credentials
from tavily import TavilyClient
import json
import pytz
import os
from firebase_config import db
from mem0 import MemoryClient

client = MemoryClient(api_key=os.environ.get("MEM0AI_API_KEY"))

def add_memory(history: list, user_id: str):
    
    client.add(history, user_id=user_id, output_format="v1.1")
    return "memory added"

def search_memory(query: str, user_id: str):
    try:
        memory = client.search(query, user_id=user_id, output_format="v1.1")
        return memory 
    except HttpError as error:
        return f"An error occurred: {error}"


#helper functions
def get_user_timezone():
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    creds = Credentials(user_info['access_token'])
    calendar_service = build('calendar', 'v3', credentials=creds)
    try:
        settings = calendar_service.settings().get(setting='timezone').execute()
        return settings['value']
    except HttpError as error:
        print(f"An error occurred while retrieving user timezone: {error}")
        return 'UTC'  # Default to UTC if unable to retrieve user's timezone

def validate_date(date_str):
       try:
           datetime.fromisoformat(date_str)
           return True
       except ValueError:
           return False

def validate_time(time_str):
       try:
           datetime.fromisoformat(time_str)
           return True
       except ValueError:
           return False

def format_event_details(event):
       start = event['start'].get('dateTime', event['start'].get('date'))
       start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
       formatted_start = start_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
       return f"- {event['summary']} ({formatted_start})"

def format_task_details(task):
       due_date = task.get('due')
       if due_date:
           due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
           formatted_due = due_dt.strftime("%Y-%m-%d")
           return f"- {task['title']} (Due: {formatted_due})"
       else:
           return f"- {task['title']} (No due date)"

def print_function_call(function_name):
        print(f"Function called: {function_name}")

# Decorator to print function calls
def log_function_call(func):
       def wrapper(*args, **kwargs):
           print_function_call(func.__name__)
           return func(*args, **kwargs)
       return wrapper

# Google Calendar API


def get_calendar_list():
    """
    Retrieve a list of calendars accessible to the user.

    Returns:
        str: A formatted string containing the list of calendars, each with its name and ID.
             Returns an error message if the request fails.

    Example:
        >>> get_calendar_list()
        "Personal Calendar (personal@example.com)
         Work Calendar (work@company.com)
         Family Calendar (family@example.com)"

    Raises:
        HttpError: If there's an issue with the Google Calendar API request.
    """
    try:
        
        user_id = UserContext.get_user_id()
        user_info = get_user_credentials(user_id)
        refreshing_token(user_id)
        creds = Credentials(user_info['access_token'],
                            refresh_token=user_info['refresh_token'],
                            token_uri=os.environ.get('TOKEN_URI'),
                            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                            )
        calendar_service = build('calendar', 'v3', credentials=creds)

        calendar_service = build('calendar', 'v3', credentials=creds)
        calendars = calendar_service.calendarList().list().execute()
        return "\n".join([f"{calendar['summary']} ({calendar['id']})" for calendar in calendars.get('items', [])])
    except HttpError as error:
        return f"An error occurred: {error}"


def create_calendar_event(summary: str, start_time: str, end_time: str, timezone:str = None, description: str = None, location: str =None, color_id: str = None, guests_can_invite_others: bool = False, recurrence: str = None, sendUpdates: str = None)-> str:
    """
    Create a new event in the user's primary Google Calendar.

    Args:
        summary (str): The title of the event.
        start_time (str): The start time of the event in ISO 8601 format (e.g., '2024-03-08T10:00:00-08:00').
        end_time (str): The end time of the event in ISO 8601 format (e.g., '2024-03-08T11:00:00-08:00').
        timezone (str, optional): The timezone for the event. If None, user's default timezone is used.
        description (str, optional): A description of the event.
        location (str, optional): The location of the event.
        color_id (str, optional): The color of the event (as defined in Google Calendar).
        guests_can_invite_others (bool, optional): Whether guests can invite other people. Defaults to False.
        recurrence (list, optional): A list of RRULE, EXRULE, RDATE and EXDATE lines for defining recurring events.
        sendUpdates (str, optional): Whether to send notifications about the creation of the event. 
                                     Options are "all", "externalOnly", or "none".

    Returns:
        str: A message indicating success and the event's HTML link, or an error message.

    Example:
        >>> create_calendar_event("Team Meeting", "2024-03-08T10:00:00-08:00", "2024-03-08T11:00:00-08:00", 
        ...                       description="Weekly team sync", location="Conference Room A")
        "Event created successfully. Link: https://www.google.com/calendar/event?eid=..."

    Raises:
        HttpError: If there's an issue with the Google Calendar API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    calendar_service = build('calendar', 'v3', credentials=creds)
    if timezone is None:
        timezone = get_user_timezone()
    if not validate_time(start_time) or not validate_time(end_time):
        return "Invalid start or end time format. Please use ISO 8601 format (e.g., 2024-03-08T10:00:00-08:00)."
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time,
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time,
            'timeZone': timezone,
        },
    }
    # Add optional fields if provided
    if description:
        event['description'] = description
    if location:
        event['location'] = location
    if color_id:
        event['colorId'] = color_id
    if guests_can_invite_others:
        event['guestsCanInviteOthers'] = guests_can_invite_others
    if sendUpdates:
        event['sendUpdates'] = sendUpdates
    if recurrence:
        event['recurrence'] = recurrence

    try:
        event = calendar_service.events().insert(calendarId="primary", body=event).execute()
        return f"Event created successfully. Link: {event.get('htmlLink')}"
    except HttpError as error:
        return f"An error occurred: {error}"


def quick_add_event(text: str, sendUpdates: str = None):
    """
    Quickly add an event to the user's primary calendar using natural language.

    Args:
        text (str): A string describing the event in natural language.
        sendUpdates (str, optional): Whether to send notifications about the creation of the event.
                                     Options are "all", "externalOnly", or "none".

    Returns:
        str: A message indicating success and the event's HTML link, or an error message.

    Example:
        >>> quick_add_event("Lunch with John tomorrow at 12pm")
        "Event created successfully. Link: https://www.google.com/calendar/event?eid=..."

    Raises:
        HttpError: If there's an issue with the Google Calendar API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    calendar_service = build('calendar', 'v3', credentials=creds)
    try:
        event = calendar_service.events().quickAdd(calendarId="primary", text=text, sendUpdates=sendUpdates).execute()
        return f"Event created successfully. Link: {event.get('htmlLink')}"
    except HttpError as error:
        return f"An error occurred: {error}"


def get_calendar_events(max_results: int = 10, query: str = None):
    """
    Retrieve a list of upcoming events from the user's primary calendar.

    Args:
        max_results (int, optional): The maximum number of events to return. Defaults to 10.
        query (str, optional): A search term to filter events. If provided, only events containing this term will be returned.

    Returns:
        str: A formatted string containing the list of events, or a message if no events are found.

    Example:
        >>> get_calendar_events(max_results=3)
        "- Team Meeting (2024-03-08 10:00:00 PST)
         - Lunch with John (2024-03-09 12:00:00 PST)
         - Project Deadline (2024-03-15 17:00:00 PST)"

    Raises:
        HttpError: If there's an issue with the Google Calendar API request.
    """
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    calendar_service = build('calendar', 'v3', credentials=creds)
    try:
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = calendar_service.events().list(calendarId="primary", timeMin=now,
                                                  maxResults=max_results, singleEvents=True,
                                                  orderBy='startTime', q=query).execute()
        events = events_result.get('items', [])
        print("events here")
        print(events)
        if not events:
            return "No upcoming events found."
        return "\n".join([format_event_details(event) for event in events])
    except HttpError as error:
        return f"An error occurred: {error}"


def delete_calendar_event(event_id: str):
    """
    Delete a specific event from the user's primary calendar.

    Args:
        event_id (str): The unique identifier of the event to be deleted.

    Returns:
        str: A message indicating success or an error message.

    Example:
        >>> delete_calendar_event("abc123xyz789")
        "Event deleted successfully."

    Raises:
        HttpError: If there's an issue with the Google Calendar API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    calendar_service = build('calendar', 'v3', credentials=creds)
    try:
        calendar_service.events().delete(calendarId="primary", eventId=event_id).execute()
        return "Event deleted successfully."
    except HttpError as error:
        return f"An error occurred: {error}"


def update_calendar_event(event_id: str, summary: str = None, start_time: str = None, end_time: str = None, timezone: str = None,
                          description: str = None, location: str = None,
                         color_id: str = None, guests_can_invite_others: bool = False,
                         recurrence: str = None, sendUpdates: str = None
                          )-> str:
    """
    Update an existing event in the user's primary calendar.

    Args:
        event_id (str): The unique identifier of the event to be updated.
        summary (str, optional): The updated title of the event.
        start_time (str, optional): The updated start time of the event in ISO 8601 format.
        end_time (str, optional): The updated end time of the event in ISO 8601 format.
        timezone (str, optional): The updated timezone for the event.
        description (str, optional): The updated description of the event.
        location (str, optional): The updated location of the event.
        color_id (str, optional): The updated color of the event.
        guests_can_invite_others (bool, optional): Whether guests can invite other people.
        recurrence (list, optional): Updated recurrence rules for the event.
        sendUpdates (str, optional): Whether to send notifications about the update.

    Returns:
        str: A message indicating success and the updated event's HTML link, or an error message.

    Example:
        >>> update_calendar_event("abc123xyz789", summary="Updated Team Meeting", location="Room 202")
        "Event updated successfully. Link: https://www.google.com/calendar/event?eid=..."

    Raises:
        HttpError: If there's an issue with the Google Calendar API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    calendar_service = build('calendar', 'v3', credentials=creds)
    if timezone is None:
        timezone = get_user_timezone()

    try:
        event = calendar_service.events().get(calendarId="primary", eventId=event_id).execute()
        if summary:
            event['summary'] = summary
        if start_time:
            if validate_time(start_time):
                event['start']['dateTime'] = start_time
            else:
                return "Invalid start time format. Please use ISO 8601 format (e.g., 2024-03-08T10:00:00-08:00)."
        if end_time:
            if validate_time(end_time):
                event['end']['dateTime'] = end_time
            else:
                return "Invalid end time format. Please use ISO 8601 format (e.g., 2024-03-08T11:00:00-08:00)."
        if description:
            event['description'] = description
        if location:
            event['location'] = location
        if color_id:
            event['colorId'] = color_id
        if guests_can_invite_others:
            event['guestsCanInviteOthers'] = guests_can_invite_others
        if sendUpdates:
            event['sendUpdates'] = sendUpdates
        if recurrence:
            event['recurrence'] = recurrence
        updated_event = calendar_service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
        return f"Event updated successfully. Link: {updated_event.get('htmlLink')}"
    except HttpError as error:
        return f"An error occurred: {error}"

# Google Tasks API


def get_task_list():
    """
    Retrieve a list of task lists accessible to the user.

    Returns:
        str: A formatted string containing the list of task lists, each with its title and ID.
             Returns an error message if the request fails.

    Example:
        >>> get_task_list()
        "Personal Tasks (ID: list123)
         Work Tasks (ID: list456)
         Shopping List (ID: list789)"

    Raises:
        HttpError: If there's an issue with the Google Tasks API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    tasks_service = build('tasks', 'v1', credentials=creds)
    try:
        task_lists = tasks_service.tasklists().list().execute()
        return "\n".join([f"{task_list['title']} (ID: {task_list['id']})" for task_list in task_lists.get('items', [])])
    except HttpError as error:
        return f"An error occurred: {error}"


def create_task(title: str, due_date: str = None, notes: str = None):
    """
    Create a new task in the user's default task list.

    Args:
        title (str): The title of the task.
        due_date (str, optional): The due date of the task in ISO 8601 format (e.g., '2024-03-15').
        notes (str, optional): Additional notes or description for the task.

    Returns:
        str: A message indicating success and the task's ID, or an error message.

    Example:
        >>> create_task("Complete project report", due_date="2024-03-15", notes="Include Q1 metrics")
        "Task created successfully. ID: task123abc"

    Raises:
        HttpError: If there's an issue with the Google Tasks API request.
    """
    
    # user_id = UserContext.get_user_id()
    user_id = "eX4uO9V5qTQn0nqEiEQ3OEKb8Fy2"
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    tasks_service = build('tasks', 'v1', credentials=creds)
    task = {
        'title': title,
        'notes': notes
    }
    if due_date:
        if validate_date(due_date):
            task['due'] = f"{due_date}T00:00:00Z"
        else:
            return "Invalid due date format. Please use ISO 8601 format (e.g., 2024-03-15)."
    try:
        
        # Get the default task list ID
        task_lists = tasks_service.tasklists().list().execute()
        # Check the number of task lists available
        if len(task_lists.get('items', [])) == 1:
            tasklist_id = task_lists['items'][0]['id']  # Use the only available task list
        elif len(task_lists.get('items', [])) >= 2:
            tasklist_id = task_lists['items'][1]['id']  # Use the second task list if available
        else:
            return "No task lists found."
        # Now, list tasks from the default list
        task = tasks_service.tasks().insert(tasklist=tasklist_id, body=task).execute()
        return f"Task created successfully. ID: {task.get('id')}"
    except HttpError as error:
        return f"An error occurred: {error}"


def get_tasks(max_results: int = 10, query: str = None):
    """
    Retrieve a list of tasks from the user's default Google Tasks list.

    Args:
        max_results (int, optional): The maximum number of tasks to return. Defaults to 10.
        query (str, optional): A search term to filter tasks. If provided, only tasks containing this term will be returned.

    Returns:
        str: A formatted string containing the list of tasks, or a message if no tasks are found.

    Example:
        >>> get_tasks(max_results=5)
        "- Complete project report (Due: 2024-03-15)
         - Prepare presentation slides (Due: 2024-03-20)
         - Schedule team meeting (No due date)"

    Raises:
        HttpError: If there's an issue with the Google Tasks API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    tasks_service = build('tasks', 'v1', credentials=creds)
    try:
        # Get the default task list ID
        task_lists = tasks_service.tasklists().list().execute()
        # Check the number of task lists available
        if len(task_lists.get('items', [])) == 1:
            tasklist_id = task_lists['items'][0]['id']  # Use the only available task list
        elif len(task_lists.get('items', [])) >= 2:
            tasklist_id = task_lists['items'][1]['id']  # Use the second task list if available
        else:
            return "No task lists found."
        # Now, list tasks from the default list
        tasks = tasks_service.tasks().list(tasklist=tasklist_id, maxResults=max_results, showCompleted=False).execute()
        task_list = tasks.get('items', [])
        if not task_list:
            return "No tasks found."
        return "\n".join([format_task_details(task) for task in task_list])
    except HttpError as error:
        return f"An error occurred: {error}"


def delete_task(task_id: str):
    """
    Delete a specific task from the user's default task list.

    Args:
        task_id (str): The unique identifier of the task to be deleted.

    Returns:
        str: A message indicating success or an error message.

    Example:
        >>> delete_task("task123abc")
        "Task deleted successfully."

    Raises:
        HttpError: If there's an issue with the Google Tasks API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    tasks_service = build('tasks', 'v1', credentials=creds)
    try:
        # Get the default task list ID
        task_lists = tasks_service.tasklists().list().execute()
        # Check the number of task lists available
        if len(task_lists.get('items', [])) == 1:
            tasklist_id = task_lists['items'][0]['id']  # Use the only available task list
        elif len(task_lists.get('items', [])) >= 2:
            tasklist_id = task_lists['items'][1]['id']  # Use the second task list if available
        else:
            return "No task lists found."
        # Now, list tasks from the default list
        tasks_service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
        return "Task deleted successfully."
    except HttpError as error:
        return f"An error occurred: {error}"


def update_task(task_id: str, title: str = None, due_date: str = None, status: str = None):
    """
    Update an existing task in the user's default task list.

    Args:
        task_id (str): The unique identifier of the task to be updated.
        title (str, optional): The updated title of the task.
        due_date (str, optional): The updated due date of the task in ISO 8601 format (e.g., '2024-03-15').
        status (str, optional): The updated status of the task (e.g., 'needsAction', 'completed').

    Returns:
        str: A message indicating success and the updated task's ID, or an error message.

    Example:
        >>> update_task("task123abc", title="Updated project report", due_date="2024-03-20")
        "Task updated successfully. ID: task123abc"

    Raises:
        HttpError: If there's an issue with the Google Tasks API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    tasks_service = build('tasks', 'v1', credentials=creds)
    try:
        # Get the default task list ID
        task_lists = tasks_service.tasklists().list().execute()
        # Check the number of task lists available
        if len(task_lists.get('items', [])) == 1:
            tasklist_id = task_lists['items'][0]['id']  # Use the only available task list
        elif len(task_lists.get('items', [])) >= 2:
            tasklist_id = task_lists['items'][1]['id']  # Use the second task list if available
        else:
            return "No task lists found."
        # Now, list tasks from the default list
        task = tasks_service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        if title:
            task['title'] = title
        if due_date:
            if validate_date(due_date):
                task['due'] = f"{due_date}T00:00:00Z"
            else:
                return "Invalid due date format. Please use ISO 8601 format (e.g., 2024-03-15)."
        if status:
            task['status'] = status
        updated_task = tasks_service.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
        return f"Task updated successfully. ID: {updated_task.get('id')}"
    except HttpError as error:
        return f"An error occurred: {error}"


def clear_tasks():
    """
    Clear all completed tasks from the user's default task list.

    Returns:
        str: A message indicating success or an error message.

    Example:
        >>> clear_tasks()
        "All completed tasks cleared successfully."

    Raises:
        HttpError: If there's an issue with the Google Tasks API request.
    """
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    tasks_service = build('tasks', 'v1', credentials=creds)
    try:
        # Get the default task list ID
        task_lists = tasks_service.tasklists().list().execute()
        # Check the number of task lists available
        if len(task_lists.get('items', [])) == 1:
            tasklist_id = task_lists['items'][0]['id']  # Use the only available task list
        elif len(task_lists.get('items', [])) >= 2:
            tasklist_id = task_lists['items'][1]['id']  # Use the second task list if available
        else:
            return "No task lists found."
        # Now, list tasks from the default list
        # Now, clear all tasks from the default list
        tasks_service.tasks().clear(tasklist=tasklist_id).execute()
        return "All tasks cleared successfully."
    except HttpError as error:
        return f"An error occurred: {error}"


def get_free_busy(start_time, end_time, calendar_ids=None):
    
    user_id = UserContext.get_user_id()
    user_info = get_user_credentials(user_id)
    refreshing_token(user_id)
    creds = Credentials(user_info['access_token'],
                        refresh_token=user_info['refresh_token'],
                        token_uri=os.environ.get('TOKEN_URI'),
                        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
                        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET')
                        )
    calendar_service = build('calendar', 'v3', credentials=creds)
    if calendar_ids is None:
        calendar_list = calendar_service.calendarList().list().execute()
        calendar_ids = [calendar['id'] for calendar in calendar_list.get('items', [])]
    
    # Ensure times are in UTC
    utc = pytz.UTC
    start_time = start_time.astimezone(utc)
    end_time = end_time.astimezone(utc)
    
    body = {
        "timeMin": start_time.isoformat(),
        "timeMax": end_time.isoformat(),
        "items": [{"id": calendar_id} for calendar_id in calendar_ids]
    }
    
    try:
        freebusy = calendar_service.freebusy().query(body=body).execute()
        return freebusy
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def find_free_time_slots(start_date, end_date, preferred_hours):
    free_slots = []
    current_date = start_date
    utc = pytz.UTC
    
    while current_date <= end_date:
        day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=utc)
        day_end = (day_start + timedelta(days=1)).replace(tzinfo=utc)
        
        preferred_start = (day_start + timedelta(hours=preferred_hours['start'])).replace(tzinfo=utc)
        preferred_end = (day_start + timedelta(hours=preferred_hours['end'])).replace(tzinfo=utc)
        
        freebusy = get_free_busy(preferred_start, preferred_end)
        
        if freebusy:
            busy_periods = []
            for calendar in freebusy['calendars'].values():
                busy_periods.extend(calendar.get('busy', []))
            
            busy_periods.sort(key=lambda x: x['start'])
            current_time = preferred_start
            
            for busy in busy_periods:
                busy_start = datetime.fromisoformat(busy['start']).replace(tzinfo=utc)
                busy_end = datetime.fromisoformat(busy['end']).replace(tzinfo=utc)
                
                if current_time < busy_start:
                    free_slots.append({
                        'start': current_time,
                        'end': busy_start
                    })
                current_time = max(current_time, busy_end)
            
            if current_time < preferred_end:
                free_slots.append({
                    'start': current_time,
                    'end': preferred_end
                })
        
        current_date += timedelta(days=1)
    
    return free_slots

def schedule_study_time(tasks: str, preferences: str, deadlines: str) -> str:
    """
    Create a study schedule based on tasks, user preferences, and deadlines.

    Args:
        tasks (str): A JSON string containing a list of tasks, each with 'title' and 'due_date' keys.
        preferences (str): A JSON string containing user preferences, including 'study_hours' with 'start' and 'end' keys.
        deadlines (str): A JSON string containing deadline information (currently unused in the function).

    Returns:
        str: A formatted string representing the created study schedule.

    Example:
        >>> tasks = '[{"title": "Math homework", "due_date": "2024-03-15"}, {"title": "History essay", "due_date": "2024-03-20"}]'
        >>> preferences = '{"study_hours": {"start": 9, "end": 17}}'
        >>> deadlines = '[]'  # Currently unused
        >>> schedule_study_time(tasks, preferences, deadlines)
        "Here's your study schedule:

         Study: Math homework
           2024-03-10 09:00 - 2024-03-10 10:00

         Review: Math homework
           2024-03-12 09:00 - 2024-03-12 09:30

         Study: History essay
           2024-03-13 09:00 - 2024-03-13 10:00

         Review: History essay
           2024-03-15 09:00 - 2024-03-15 09:30"

    Note:
        This function creates a schedule for the next 7 days, allocating 1-hour study sessions and 30-minute review sessions.
        It saves the created schedule to the user's document in Firestore.
    """
    tasks = json.loads(tasks)
    preferences = json.loads(preferences)
    deadlines = json.loads(deadlines)

    tasks.sort(key=lambda x: datetime.fromisoformat(x['due_date']))

    schedule = []
    current_date = datetime.now(pytz.UTC).date()
    end_date = current_date + timedelta(days=7)

    free_slots = find_free_time_slots(current_date, end_date, preferences['study_hours'])

    for task in tasks:
        task_deadline = datetime.fromisoformat(task['due_date']).replace(tzinfo=pytz.UTC).date()
        task_slots = [slot for slot in free_slots if slot['start'].date() <= task_deadline]
        
        if task_slots:
            slot = task_slots[0]
            study_session = {
                'type': 'study',
                'task': task['title'],
                'start': slot['start'],
                'end': min(slot['end'], slot['start'] + timedelta(hours=1))
            }
            schedule.append(study_session)
            
            if study_session['end'] == slot['end']:
                free_slots.remove(slot)
            else:
                slot['start'] = study_session['end']
            
            review_date = study_session['start'].date() + timedelta(days=2)
            review_slots = [s for s in free_slots if s['start'].date() == review_date]
            if review_slots:
                review_slot = review_slots[0]
                review_session = {
                    'type': 'review',
                    'task': task['title'],
                    'start': review_slot['start'],
                    'end': min(review_slot['end'], review_slot['start'] + timedelta(minutes=30))
                }
                schedule.append(review_session)
                
                if review_session['end'] == review_slot['end']:
                    free_slots.remove(review_slot)
                else:
                    review_slot['start'] = review_session['end']

    save_schedule(schedule)
    return format_schedule(schedule)

def save_schedule(schedule: list) -> str:
    try:
        user_id = UserContext.get_user_id()
        # Reference to the user's document
        user_ref = db.collection('users').document(user_id).collection('schedule')
        
        # Convert datetime objects to strings for Firestore
        firestore_schedule = []
        for session in schedule:
            firestore_session = session.copy()
            firestore_session['start'] = session['start'].isoformat()
            firestore_session['end'] = session['end'].isoformat()
            firestore_schedule.append(firestore_session)
        
        # Save the schedule to the user's document
        user_ref.set({'schedule': firestore_schedule}, merge=True)
        
        return "Schedule saved successfully."
    except Exception as e:
        return f"An error occurred while saving the schedule: {str(e)}"

def format_schedule(schedule):
    formatted = "Here's your study schedule:\n\n"
    for session in schedule:
        formatted += f"{session['type'].capitalize()}: {session['task']}\n"
        formatted += f"  {session['start'].strftime('%Y-%m-%d %H:%M')} - {session['end'].strftime('%Y-%m-%d %H:%M')}\n\n"
    return formatted

def get_saved_schedule():
    """
    Get the saved schedule for the user.

    Returns:
        list: A list of study sessions saved for the user.

    Raises:
        Exception: If there's an error retrieving the schedule.
    """
    try:
        # Reference to the user's document
        
        user_id = UserContext.get_user_id()
    
        user_ref = db.collection('users').document(user_id).collection('schedule')
        print(user_ref)
        print('after user ref')
        
        # Get the user's document
        user_doc = user_ref.get()
        
        if user_doc.exists:
            firestore_schedule = user_doc.to_dict().get('schedule', [])
            
            # Convert string timestamps back to datetime objects
            schedule = []
            for session in firestore_schedule:
                session_copy = session.copy()
                session_copy['start'] = datetime.fromisoformat(session['start'])
                session_copy['end'] = datetime.fromisoformat(session['end'])
                schedule.append(session_copy)
            
            return schedule
        else:
            return []
    except Exception as e:
        raise Exception(f"An error occurred while retrieving the schedule: {str(e)}")

def search_web(query: str) -> str:
    """
    Search the web for information.

    Args:
        query (str): The search query.

    Returns:
        str: A formatted string containing the search results.
    """
    client = TavilyClient(api_key=os.environ.get('TAVILY_API_KEY'))
    response = client.search(query)
    return response

