from flask import Flask, request, jsonify, redirect, render_template, session, abort
import openai
from traceback import format_exc
import time
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import datetime
from openai import OpenAI
from pytz import timezone
import random
import logging
import os
import pathlib
import string
import random
from google.auth.transport.requests import Request

app = Flask(__name__)
app.secret_key = "0509Maxi."

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
GOOGLE_CLIENT_ID = "803791243229-tphm5c2513khcqsrqt493r0qr1tsog59.apps.googleusercontent.com"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
flow = Flow.from_client_secrets_file(client_secrets_file, SCOPES, redirect_uri='http://127.0.0.1:5000/callback')

service = None

def login_is_required(function):
    def wrapper_login_required(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()
    return wrapper_login_required

@app.route("/chatbot")
@login_is_required
def chatbot():
    global service
    creds = None
    if 'credentials' in session:
        creds = Credentials.from_authorized_user_info(session['credentials'])
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(client_secrets_file, SCOPES, redirect_uri='http://127.0.0.1:5000/callback')
            authorization_url, _ = flow.authorization_url(prompt='consent')
            return redirect(authorization_url)
    session['credentials'] = credentials_to_dict(creds)
    
    # Initialize the service object with the obtained credentials
    service = build('calendar', 'v3', credentials=creds)
    
    return render_template("chatbot.html")

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }


booked_appointments = []

def suggest_free_slots():
    # Hole das aktuelle Datum und die Uhrzeit in der Zeitzone Europe/Berlin
    berlin_timezone = timezone('Europe/Berlin')
    now = datetime.datetime.now(berlin_timezone)
    
    # Setze die Start- und Endzeit für heute und morgen
    today_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    tomorrow_start = (now + datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    tomorrow_end = (now + datetime.timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
    
    # Hole die Liste der Ereignisse für heute und morgen
    today_events_str = get_events(today_start.isoformat(), today_end.isoformat())
    tomorrow_events_str = get_events(tomorrow_start.isoformat(), tomorrow_end.isoformat())
    
    # Konvertiere die Ereignisse von einer Zeichenkette zurück zu einer Liste von Dictionaries
    today_events = []
    if today_events_str != "No events found.":
        for event_str in today_events_str.split("\n"):
            start = event_str.split(" to ")[0].split("Event from ")[1]
            end = event_str.split(" to ")[1]
            today_events.append({
                "start": start,
                "end": end
            })
    
    tomorrow_events = []
    if tomorrow_events_str != "No events found.":
        for event_str in tomorrow_events_str.split("\n"):
            start = event_str.split(" to ")[0].split("Event from ")[1]
            end = event_str.split(" to ")[1]
            tomorrow_events.append({
                "start": start,
                "end": end
            })
    
    # Generiere freie Zeitfenster für heute
    today_slots = []
    current_time = today_start
    while current_time < today_end:
        slot_start = current_time
        slot_end = slot_start + datetime.timedelta(minutes=30)
        
        # Überprüfe, ob das Zeitfenster mit gebuchten Terminen überlappt
        overlaps = False
        for event in today_events:
            event_start = datetime.datetime.fromisoformat(event['start'])
            event_end = datetime.datetime.fromisoformat(event['end'])
            if (slot_start < event_end) and (slot_end > event_start):
                overlaps = True
                break
        
        if not overlaps and slot_start > now:
            today_slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat()
            })
        
        current_time += datetime.timedelta(minutes=30)
    
    # Generiere freie Zeitfenster für morgen
    tomorrow_slots = []
    current_time = tomorrow_start
    while current_time < tomorrow_end:
        slot_start = current_time
        slot_end = slot_start + datetime.timedelta(minutes=30)
        
        # Überprüfe, ob das Zeitfenster mit gebuchten Terminen überlappt
        overlaps = False
        for event in tomorrow_events:
            event_start = datetime.datetime.fromisoformat(event['start'])
            event_end = datetime.datetime.fromisoformat(event['end'])
            if (slot_start < event_end) and (slot_end > event_start):
                overlaps = True
                break
        
        if not overlaps:
            tomorrow_slots.append({
                "start": slot_start.isoformat(),
                "end": slot_end.isoformat()
            })
        
        current_time += datetime.timedelta(minutes=30)
    
    # Wähle die vorgeschlagenen Zeitfenster basierend auf der Verfügbarkeit
    if today_slots and len(today_slots) >= 3:
        suggested_slots = today_slots[:3]
    else:
        suggested_slots = tomorrow_slots[:3]
    
    # Formatiere die vorgeschlagenen Zeitfenster als Zeichenkette
    if suggested_slots:
        slot_times = []
        for slot in suggested_slots:
            start_time = datetime.datetime.fromisoformat(slot['start'])
            slot_times.append(start_time.strftime('%H:%M'))
        
        if suggested_slots[0]['start'].startswith(now.strftime('%Y-%m-%d')):
            return f"Hier sind meine Vorschläge für unseren Termin heute: {', '.join(slot_times)} Uhr. Welcher Zeitpunkt passt dir am besten?"
        else:
            return f"Hier sind meine Vorschläge für unseren Termin morgen: {', '.join(slot_times)} Uhr. Welcher Zeitpunkt passt dir am besten?"
    else:
        return "Entschuldige, aber ich habe heute und morgen leider keine freien Termine mehr. Bitte schau zu einem späteren Zeitpunkt nochmal nach oder lass mich wissen, wenn du noch andere Fragen hast."

def create_event(event):
    global service
    if service is None:
        raise ValueError("Calendar service is not initialized.")
    
    # Überprüfe auf überlappende Ereignisse
    start_time = event['start']['dateTime']
    end_time = event['end']['dateTime']
    conflicts = get_conflicts(start_time, end_time)
    
    if conflicts:
        return f"Entschuldigung, aber der gewählte Zeitraum überschneidet sich mit folgenden Terminen:\n{conflicts}\nBitte wähle einen anderen Zeitpunkt."
    else:
        event = service.events().insert(calendarId='maximilianradomski@gmail.com', body=event).execute()
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event['summary']
        return f"Termin erstellt: {summary} von {start} bis {end}"

def get_conflicts(start_time, end_time):
    # Überprüfe auf überlappende Ereignisse in der Liste der gebuchten Termine
    conflicts = []
    for appointment in booked_appointments:
        if (start_time < appointment['end']) and (end_time > appointment['start']):
            conflicts.append(appointment)
    
    if conflicts:
        conflict_details = []
        for conflict in conflicts:
            start = conflict['start']
            end = conflict['end']
            summary = conflict['summary']
            conflict_details.append(f"- {start} bis {end}: {summary}")
        
        return "\n".join(conflict_details)
    else:
        return ""

def send_calendar_link(calendar_link=None):
    if calendar_link is None:
        calendar_link = 'https://calendar.app.google/iHxGb2B3D6V1arUX7'
    message = f"Hier ist der Link zu meinem Google Calendar Booking: {calendar_link}"
    return message
def get_event(event_id):
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    return event

def update_event(event_id, updated_event):
    event = service.events().update(calendarId='primary', eventId=event_id, body=updated_event).execute()
    return event

def delete_event(event_id):
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return f"Event with ID {event_id} deleted successfully."

def get_events(start_time, end_time):
    events_result = service.events().list(calendarId='primary', timeMin=start_time, timeMax=end_time,
                                          maxResults=100, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    
    if not events:
        return "No events found."
    
    formatted_events = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        formatted_events.append(f"Event from {start} to {end}")
    
    return "\n".join(formatted_events)

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


@app.route("/login")
def login():
    state = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    session['state'] = state
    authorization_url, _ = flow.authorization_url(state=state)
    return redirect(authorization_url)

@app.route("/callback")
def callback():
    state = session.get('state')
    received_state = request.args.get('state')
    app.logger.info(f"Session state: {state}, Received state: {received_state}")

    try:
        flow.fetch_token(authorization_response=request.url, state=state)
    except Exception as e:
        app.logger.error(f"Error during token fetching: {e}")
        app.logger.error(f"Full traceback: {format_exc()}")
        return "An error occurred during authentication.", 500
    credentials = flow.credentials
    session["credentials"] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return redirect("/chatbot")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chatbot", methods=["POST"], endpoint="chatbot_api")
@login_is_required
def chatbot_api():
    data = request.get_json()
    user_input = data["message"]
    chat_history.append({"role": "user", "content": user_input})

    # Initialize the client
    client = openai.OpenAI(api_key="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")
    assistant_id = "asst_aDHEdGjng0sZP7qooUiWSBiz"

    try:
        # Step 1: Create a Thread
        thread = client.beta.threads.create()

        # Step 3: Add the prompt as a Message to the Thread
        chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        prompt = f"""
        Ich bin Max, ein Experte für Immobilien in Bali. Mein Ziel ist es, dir dabei zu helfen, die perfekte Investitionsmöglichkeit zu finden.

        Aufgaben:

        Kommuniziere auf Deutsch
        Führe professionelle Gespräche
        Hebe die Vorteile einer Investition in Bali hervor
        Stelle Fragen, um die Bedürfnisse des Kunden zu verstehen
        Teile relevante Erfolgsgeschichten
        Vermittle ein Gefühl von Chance und Dringlichkeit
        Verwende immer Funktionsaufrufe für zeitbezogene Aufgaben
        Bevor ein Termin vorgeschlagen oder eingetragen wird, überprüfe mit der get_events-Funktion, welche Zeitfenster verfügbar sind, um Überschneidungen zu vermeiden
        Wenn es für den aktuellen Tag bereits spät ist, schlage Termine für den nächsten Tag vor. Der Tag für Calls geht von 8 Uhr deutscher Zeit bis 16 Uhr deutscher Zeit
        Vermeide Doppelbuchungen, indem du vor dem Vorschlagen eines Termins die Verfügbarkeit überprüfst
        Schlage die besten verfügbaren Zeiten für ein Telefonat basierend auf deinem Zeitplan vor (nur deutsche Zeit, ohne Erwähnung der Bali-Zeit)
        Format Beispiel: "Ich habe um 12, 15 oder 20 Uhr Zeit für dich. Welche Zeit passt dir am besten?"
        Wenn der Benutzer eine bestimmte Zeit angibt, verwende sofort den create_event-Funktionsaufruf, um den Termin direkt zum Google Kalender hinzuzufügen (immer in deutscher Zeitzone), sofern der Slot frei ist
        Füge den Termin direkt hinzu, ohne auf weitere Bestätigung zu warten, wenn der Slot verfügbar ist
        Informiere den Benutzer, dass der Termin erfolgreich geplant wurde oder dass der gewünschte Slot bereits belegt ist
        Wenn alle Termine für den heutigen Tag voll sind oder der Benutzer keine Zeit hat, frage, ob er einen Termin an einem anderen Tag machen möchte
        Wenn der Benutzer auch an einem anderen Tag keine Zeit hat oder keinen Termin machen möchte, gib ihm diesen Google Calendar Link, damit er einen Termin machen kann, wann immer er will: https://calendar.app.google/iHxGb2B3D6V1arUX7
        Gehe auf Bedenken ein und zeige, warum Bali eine kluge Investition ist
        Verfolge mit personalisierten Nachrichten nach
        Lenke das Gespräch in Richtung Vereinbarung eines Anrufs
        Verkaufsrahmen:

        Aufmerksamkeit: Fesselnder Einstieg, der Interesse weckt
        Interesse: Teile die wichtigsten Merkmale und Vorteile
        Verlangen: Beschreibe den Lebensstil und das Potenzial in Bali
        Handlung: Führe zur Vereinbarung eines Anrufs, um weitere Einzelheiten zu besprechen
        Funktionsaufrufe (Obligatorisch):

        Verwende geeignete Funktionsaufrufe für alle Aufgaben
        send_calendar_link: Sende dem Benutzer den Link zu deinem Google Kalender, falls er keine Zeit hat oder ihm die Termine nicht passen.Sobald der user sagt er hat keine zeit schick ihm umgehend den link. Schick den link sobald der user einen anderen termin will oder keine zeit hat
        get_events: Hole die Liste der Ereignisse, um verfügbare Zeitfenster zu ermitteln und Überschneidungen zu vermeiden. Lasse niemals Doppelbuchungen zu.
        Wenn keine Ereignisse gefunden werden, gebe "No events found." zurück und nutze dann die create_event Funktion, um ein Event zu kreieren.
        Wenn ein Ergebnis gefunden wird, gebe "Events found" zurück und buche keinen Termin, sondern sag dem User, dass du zu der gewünschten Zeit keine Verfügbarkeit hast.
        suggest_free_slots: Finde die besten verfügbaren Zeiten für eine Verbindung basierend auf dem bevorzugten Datum und mache nur Termine, die mindestens eine Stunde von der aktuellen Zeit entfernt sind (gehe vom aktuellen Datum aus, wenn nicht angegeben). Schlage niemals belegte Slots vor.
        Formatiere die Ausgabe als: "Ich habe morgen um (erste Uhrzeit), (zweite Uhrzeit), (dritte Uhrzeit) Uhr Zeit für dich. Welche Zeit passt dir am besten?"
        create_event: Plane den Anruf sofort im Kalender ein, wenn der Benutzer selbst eine Zeit angibt (immer in deutscher Zeitzone) und der Slot frei ist. Keine weitere Bestätigung erforderlich. Wenn der Slot belegt ist, informiere den Benutzer darüber.
        update_event: Verschiebe den Anruf bei Bedarf
        delete_event: Storniere den Anruf und entferne ihn aus dem Kalender. Lösche niemals ein Event.
        get_current_datetime_and_timezone: Hole das aktuelle Datum und die Uhrzeit in deutscher Zeit für eine genaue Planung
        Wenn ein Datum ohne Jahr erwähnt wird, gehe vom aktuellen Jahr aus get_current_datetime_and_timezone aus
        Ich werde durchgängig die erforderlichen Funktionsaufrufe für zeitbezogene Aufgaben verwenden, um eine ordnungsgemäße Integration in Google Calendar zu gewährleisten.

        Während des gesamten Chats werde ich einen professionellen Ton beibehalten und das Gespräch in Richtung Vereinbarung eines Anrufs lenken. Alle Zeiten basieren ausschließlich auf der deutschen Zeit, ohne Erwähnung der Bali-Zeit.
        
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
            if run_status.status == "completed":
                messages = client.beta.threads.messages.list(
                    thread_id=thread.id
                )

                # Get the assistant's response
                assistant_response = messages.data[0].content[0].text.value
                chat_history.append({"role": "assistant", "content": assistant_response})

                return jsonify({"response": assistant_response})

            elif run_status.status == "requires_action":
                print("Function Calling")
                required_actions = run_status.required_action.submit_tool_outputs.model_dump()
                print(required_actions)
                tool_outputs = []
                import json
                for action in required_actions["tool_calls"]:
                    func_name = action["function"]["name"]
                    arguments = json.loads(action["function"]["arguments"])
                    if func_name == "create_event":
                        output = create_event(event=arguments["event"])
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "get_event":
                        output = get_event(event_id=arguments["event_id"])
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "update_event":
                        output = update_event(event_id=arguments["event_id"], updated_event=arguments["updated_event"])
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "delete_event":
                        output = delete_event(event_id=arguments["event_id"])
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "get_conflicts":
                        output = get_conflicts(start_time=arguments["start_time"], end_time=arguments["end_time"])
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "get_events":
                        output = get_events(start_time=arguments["start_time"], end_time=arguments["end_time"])
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "get_current_datetime_and_timezone":
                        output = get_current_datetime_and_timezone()
                        output_str = json.dumps(output)
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output_str
                        })
                    elif func_name == "suggest_free_slots":
                        output = suggest_free_slots()
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
                        })
                    elif func_name == "get_next_dates_and_weekdays":
                        num_days = arguments.get("num_days", 7)
                        output = get_next_dates_and_weekdays(num_days)
                        output_str = json.dumps(output)
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output_str
                        })
                    elif func_name == "send_calendar_link":
                        calendar_link = arguments.get("calendar_link", None)
                        output = send_calendar_link(calendar_link)
                        tool_outputs.append({
                            "tool_call_id": action["id"],
                            "output": output
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
        return jsonify({"error": "An error occurred while processing your request."}), 500
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(port=5000, debug=True)
