from flask import Flask, request, jsonify
import openai
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime
from openai import OpenAI
from pytz import timezone
import logging
app = Flask(__name__)

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
creds = flow.run_local_server(port=0)
service = build('calendar', 'v3', credentials=creds)

def suggest_free_slots():
    # Get the current date and time in Europe/Berlin timezone
    berlin_timezone = timezone('Europe/Berlin')
    now = datetime.datetime.now(berlin_timezone)
    
    # Round the current time to the nearest 15 minutes
    current_time = now.replace(minute=now.minute // 15 * 15, second=0, microsecond=0)
    
    # Set the start and end times for the next 7 days
    start_time = current_time.isoformat()
    end_time = (current_time + datetime.timedelta(days=7)).isoformat()
    
    # Get the list of events in the next 7 days
    events = get_events(start_time, end_time)
    
    # Generate free time slots
    free_slots = []
    while current_time < now + datetime.timedelta(days=7):
        # Check if the current time slot is available
        slot_start = current_time
        slot_end = slot_start + datetime.timedelta(minutes=30)
        
        # Check if the time slot overlaps with any existing events
        overlaps = False
        for event in events:
            event_start = datetime.datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            event_end = datetime.datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))
            if (slot_start < event_end) and (slot_end > event_start):
                overlaps = True
                break
        
        if not overlaps:
            free_slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat()
            })
        
        current_time += datetime.timedelta(minutes=30)
    
    # Select the first 3 free slots
    suggested_slots = free_slots[:3]
    
    # Format the suggested slots as a string
    if suggested_slots:
        slot_details = []
        for slot in suggested_slots:
            start_time = datetime.datetime.fromisoformat(slot['start'])
            end_time = datetime.datetime.fromisoformat(slot['end'])
            slot_details.append(f"- {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%H:%M')}")
        
        return "Here are some available time slots for an appointment:\n" + "\n".join(slot_details) + "\nPlease let me know if any of these time slots work for you, or if you prefer a different time."
    else:
        return "I apologize, but there are no available time slots for an appointment in the next 7 days. Please check back later or let me know if you have any other questions."

def create_event(event):
    # Set the timezone for the event
    event['start']['timeZone'] = 'Europe/Berlin'
    event['end']['timeZone'] = 'Europe/Berlin'
    
    event = service.events().insert(calendarId='primary', body=event).execute()
    start = event['start'].get('dateTime', event['start'].get('date'))
    end = event['end'].get('dateTime', event['end'].get('date'))
    summary = event['summary']
    return f"Event created: {summary} from {start} to {end}"

def get_event(event_id):
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    return event

def update_event(event_id, updated_event):
    event = service.events().update(calendarId='primary', eventId=event_id, body=updated_event).execute()
    return event

def delete_event(event_id):
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return f"Event with ID {event_id} deleted successfully."

def get_conflicts(start_time, end_time):
    events_result = service.events().list(calendarId='primary', timeMin=start_time, timeMax=end_time,
                                          maxResults=100, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

def get_events(start_time, end_time):
    events_result = service.events().list(calendarId='primary', timeMin=start_time, timeMax=end_time,
                                          maxResults=100, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    
    if not events:
        return []  # Return an empty list if no events are found
    
    event_details = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event['summary']
        event_details.append(f"- {start}: {summary}")
    
    return events  # Return the list of events

def get_current_datetime_and_timezone():
    berlin_timezone = timezone('Europe/Berlin')
    now = datetime.datetime.now(berlin_timezone)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": now.strftime("%A"),
        "day": now.strftime("%d"),
        "month": now.strftime("%B"),
        "year": now.strftime("%Y"),
        "timezone": "Europe/Berlin"
    }

def get_next_dates_and_weekdays(num_days=7):
    current_date = datetime.datetime.now(timezone('Europe/Berlin'))
    dates_and_weekdays = []
    for i in range(num_days):
        next_date = current_date + datetime.timedelta(days=i)
        dates_and_weekdays.append({
            "date": next_date.strftime("%Y-%m-%d"),
            "weekday": next_date.strftime("%A")
        })
    return dates_and_weekdays

chat_history = []

@app.route('/api/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    user_input = data['message']
    chat_history.append({"role": "user", "content": user_input})

    # Initialize the client
    client = openai.OpenAI(api_key="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")
    assistant_id = 'asst_s8bBrzftO6ZU9Ij33noyNwTJ'

    try:
        # Step 1: Create a Thread
        thread = client.beta.threads.create()

        # Step 3: Add the prompt as a Message to the Thread
        chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        prompt = f"""
    I am Max, your friendly neighborhood real estate guru specializing in the most incredible properties in Bali! I'm here to help you discover your dream lifestyle and make it a reality. Let's dive into this exciting world together and find the perfect investment opportunity for you!

    Key Responsibilities:

    Keep the conversation fun, engaging, and totally casual, just like chatting with your best bud!
    Use my charm and wit to paint a picture of the amazing life you could have in Bali.
    Ask you thought-provoking questions to help you realize why investing in Bali is the smartest move you could make.
    Share stories that'll make you feel like you're already living the high life in your very own Balinese paradise.
    Create a sense of excitement and urgency, so you'll want to act fast and seize this once-in-a-lifetime opportunity.
    Suggest the perfect times for us to connect over a call, all based on your schedule and German time, of course!
    Address any concerns you might have and show you why investing in Bali is a total no-brainer.
    Follow up with personalized reminders and messages to keep you motivated and on track.
    Guide our conversation in a natural way towards setting up a call, so we can make your dreams a reality.
    AIDA Marketing Framework:

    Grab your attention with an irresistible opening that'll make you want to learn more.
    Pique your interest by sharing all the incredible features and benefits of these luxurious properties.
    Create a burning desire for the lifestyle you could have by painting a vivid picture of your dream life in Bali.
    Guide you towards taking action by suggesting the best times for us to chat and make it happen.
    Proactive Call Scheduling:
    - Keep an eye out for the perfect moments in our conversation to suggest a call, so it feels natural and exciting.
    - When you mention a specific day or show interest, I'll use my magic 'suggest_free_slots' function to find the best times for us to connect.
    - Double-check with my trusty 'get_current_datetime_and_timezone' function to ensure our call is always scheduled at the perfect time for you, in German time.
    - Use the current date information to provide accurate day and date references when suggesting call times.
    - Confidently offer you three amazing options for our call, making it feel like an exclusive opportunity to explore these incredible properties together.
    - Once you've picked the best time for you, I'll use my 'create_event' function to lock it in and make it official!
    - Send you a confirmation of our scheduled call, with all the details in German time, so you're always in the loop.
    
    Function Calls:
    Whenever we're planning, rescheduling, or canceling calls, I'll use my handy functions to make it a breeze:
    - 'suggest_free_slots': Finds the best times for us to connect and chat on the user's preferred date. If no specific date is mentioned, assume the current date.
    - 'create_event': Makes our call official by adding it to the calendar.
    - 'update_event': Allows us to easily reschedule if needed, so it's always convenient for you.
    - 'delete_event': Cancels our call and removes it from the calendar, if necessary.
    - 'get_current_datetime_and_timezone': Keeps me on top of the current date and time in German time, so I'm always suggesting the best options for you.
    - When asked about a specific date without a year, assume the current year from 'get_current_datetime_and_timezone' to provide accurate weekday information.
        
    Throughout our chat, I'll keep things fun, engaging, and totally natural, while subtly guiding us towards setting up a call using my persuasion skills and the AIDA framework. And don't worry, I'll make sure all the times we discuss are in German time, so there's never any confusion!
            
        Chat History:
        {chat_history_str}
        User: {user_input}
        Assistant:"""

        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        # Step 3: Run the Assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,            
            assistant_id=assistant_id,
        )

        while True:
            # Wait for 5 seconds
            time.sleep(5)

            # Retrieve the run status
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

            # If run is completed, get messages
            if run_status.status == 'completed':
                messages = client.beta.threads.messages.list(
                    thread_id=thread.id
                )

                # Get the assistant's response
                assistant_response = messages.data[0].content[0].text.value
                chat_history.append({"role": "assistant", "content": assistant_response})

                return jsonify({'response': assistant_response})

            elif run_status.status == 'requires_action':
                print("Function Calling")
                required_actions = run_status.required_action.submit_tool_outputs.model_dump()
                print(required_actions)
                tool_outputs = []
                import json
                for action in required_actions["tool_calls"]:
                    func_name = action['function']['name']
                    arguments = json.loads(action['function']['arguments'])
                    if func_name == "create_event":
                        output = create_event(event=arguments['event'])
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_event":
                        output = get_event(event_id=arguments['event_id'])
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "update_event":
                        output = update_event(event_id=arguments['event_id'], updated_event=arguments['updated_event'])
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "delete_event":
                        output = delete_event(event_id=arguments['event_id'])
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_conflicts":
                        output = get_conflicts(start_time=arguments['start_time'], end_time=arguments['end_time'])
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_events":
                        output = get_events(start_time=arguments['start_time'], end_time=arguments['end_time'])
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_current_datetime_and_timezone":
                        output = get_current_datetime_and_timezone()
                        output_str = json.dumps(output)
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output_str
                        })
                    elif func_name == "suggest_free_slots":
                        output = suggest_free_slots()
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output
                        })
                    elif func_name == "get_next_dates_and_weekdays":
                        num_days = arguments.get('num_days', 7)
                        output = get_next_dates_and_weekdays(num_days)
                        output_str = json.dumps(output)
                        tool_outputs.append({
                            "tool_call_id": action['id'],
                            "output": output_str
                        })
                    else:
                        raise ValueError(f"Unknown function: {func_name}")

                print("Submitting outputs back to the Assistant...")
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
            else:
                print("Waiting for the Assistant to process...")
                time.sleep(5)

    except openai.APIError as e:
        logging.error(f"OpenAI API Error: {e}")
        return jsonify({'error': 'An error occurred while processing your request.'}), 500
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return jsonify({'error': 'An unexpected error occurred.'}), 500

if __name__ == '__main__':
    app.run(port=5000)