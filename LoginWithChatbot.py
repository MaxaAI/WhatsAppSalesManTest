from flask import Flask, request, jsonify, redirect, render_template, session, abort, url_for
import openai
from traceback import format_exc
import requests
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
from flask_migrate import Migrate
import string
import random
from google.auth.transport.requests import Request
from flask_sqlalchemy import SQLAlchemy
from functools import wraps

app = Flask(__name__)
# Your SQLAlchemy database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///neue_datenbank.db' 
db = SQLAlchemy(app)
migrate = Migrate(app, db)
app.secret_key = "0509Maxi."

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    google_access_token = db.Column(db.String(255), nullable=True)
    google_refresh_token = db.Column(db.String(255), nullable=True)
    # Make sure this line is present in your User model
    thread_id = db.Column(db.String(255), nullable=True)  # This is the missing attribute

    def __repr__(self):
        return '<User %r>' % self.email
    
    
with app.app_context():
    db.create_all()

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.String(1024), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return '<ChatMessage {}>'.format(self.content)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
GOOGLE_CLIENT_ID = "803791243229-tphm5c2513khcqsrqt493r0qr1tsog59.apps.googleusercontent.com"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

# Google Calendar API setup
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]
flow = Flow.from_client_secrets_file(client_secrets_file, SCOPES, redirect_uri='http://127.0.0.1:5000/callback')

service = None

def login_is_required(function):
    @wraps(function)
    def wrapper_login_required(*args, **kwargs):
        if "user_id" not in session:  # Verwenden Sie 'user_id' zur Überprüfung
            return abort(401)  # Nicht autorisiert
        else:
            return function(*args, **kwargs)
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
    
    service = build('calendar', 'v3', credentials=creds)
    return render_template("chatbot.html")

@app.route('/buy_full_version', methods=['GET', 'POST'])
def purchase_full_version():
    if request.method == 'POST':
        client_secret_file = request.files['client_secret']
        phone_number = request.form['phone_number']

        # Hier können Sie die erhaltenen Daten verarbeiten
        # Zum Beispiel: Speichern Sie die Daten in der Datenbank und weisen Sie den Chatbot dem Benutzer zu

        return redirect(url_for('success'))  # Leiten Sie zu einer Erfolgsmeldung oder einer anderen Seite weiter

    return render_template('buy_full_version.html')

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
    global service
    if service is None:
        return "Error: Google Calendar Service ist nicht initialisiert."

    today_events_str = get_events(service, today_start.isoformat(), today_end.isoformat())
    tomorrow_events_str = get_events(service, tomorrow_start.isoformat(), tomorrow_end.isoformat())

    
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
        user = event['creator']['email']
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        summary = event['summary']
        return f"Termin erstellt: {summary} von {start} bis {end} mit {user}"

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

def get_events(service, start_time, end_time):
    
    print(f"Fetching events between {start_time} and {end_time}")
    try:
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
    except Exception as e:
        print(f"Error fetching events: {e}")  # Improved error handling
        return "Error fetching events."
    
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

@app.route("/user/<int:user_id>/chat_history")
@login_is_required
def view_chat_history(user_id):
    if session.get('user_id') != user_id:
        abort(403)  # Forbidden access if the logged-in user ID doesn't match the requested user ID

    chat_history = ChatMessage.query.filter_by(user_id=user_id).order_by(ChatMessage.timestamp).all()
    return render_template('chat_history.html', chat_history=chat_history)

@app.route("/login")
def login():
    state = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    session['state'] = state
    authorization_url, _ = flow.authorization_url(state=state)
    return redirect(authorization_url)

@app.route("/emails")
def list_emails():
    users = User.query.all()
    emails = [user.email for user in users]
    return jsonify(emails)

def get_user_info(credentials):
    userinfo_endpoint = 'https://openidconnect.googleapis.com/v1/userinfo'
    headers = {'Authorization': f'Bearer {credentials.token}'}
    response = requests.get(userinfo_endpoint, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        app.logger.error(f"Failed to get user info: {response.content}")
        response.raise_for_status()

@app.route("/callback")
def callback():
    # Retrieve the state from the session to compare with the state returned in the query string
    state = session.get('state')
    received_state = request.args.get('state')

    # Log the received state for debugging purposes
    app.logger.info(f"Session state: {state}, Received state: {received_state}")

    try:
        # Attempt to fetch the token using the authorization response URL
        flow.fetch_token(authorization_response=request.url)

        # At this point, flow.credentials will have been populated
        credentials = flow.credentials

        # Store the credentials in the session
        session["credentials"] = credentials_to_dict(credentials)

            # Verify the ID token is present in the credentials
        if credentials.id_token is None:
            raise ValueError("ID Token is missing in the credentials")

            # Fetch the user's info using the token
        userinfo = get_user_info(credentials)

            # Extract the email from the userinfo
        user_email = userinfo.get('email')

            # Nach erfolgreicher Authentifizierung
        user = User.query.filter_by(email=user_email).first()
        if not user:
                # Wenn kein Benutzer existiert, erstelle einen neuen mit den Tokens
                user = User(email=user_email, google_access_token=credentials.token, google_refresh_token=credentials.refresh_token)
                db.session.add(user)
        else:
                # Wenn der Benutzer existiert, aktualisiere die Tokens
                user.google_access_token = credentials.token
                user.google_refresh_token = credentials.refresh_token
        db.session.commit()

        session['user_id'] = user.id  # Stellen Sie sicher, dass die User ID hier gespeichert wird


        # Redirect the user to the chatbot page
        return redirect("/chatbot")

    except Exception as e:
        # Log the exception and return an error message
        app.logger.error(f"Error during the callback process: {e}")
        app.logger.error(f"Full traceback: {format_exc()}")
        return "An error occurred during authentication.", 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin/emails", endpoint="admin_emails")
@login_is_required
def admin_emails():
    users = User.query.all()
    return render_template("admin_emails.html", users=users)

chat_histories = {}

@app.route("/api/chatbot", methods=["POST"])
@login_is_required
def chatbot_api():

    client = openai.OpenAI(api_key="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")
    assistant_id = "asst_srCXZw0EUitQ9Ha57UyKAHIj"

    data = request.get_json()
    user_input = data["message"]

    # Stellen Sie sicher, dass 'user_id' in der Session vorhanden ist
    if 'user_id' not in session:
        return jsonify({"error": "User not properly authenticated"}), 401

    user_id = session['user_id']

    # Holen Sie das User-Objekt und die zugehörige thread_id aus der Datenbank
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Wenn es keine thread_id gibt, erstellen Sie eine neue für diesen Benutzer
    if not user.thread_id:
        thread = client.beta.threads.create()
        user.thread_id = thread.id
        chat_histories[user.thread_id] = []  # Initialize empty chat history for this thread
        db.session.commit()

    # Retrieve the user's chat history
    user_chat_history = chat_histories.get(user.thread_id, [])

    try:
        # Step 1: Create a Thread
        thread = client.beta.threads.create()

        # Step 3: Add the prompt as a Message to the Thread
        chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        # prompt = f"""{chat_history_str}\nUser: {user_input}\nAssistant:"
        # Du bist ein Onboarder der Bali invest. Interagiere mit dem user und dem ziel einen anruf zu vereinbaren.

        # Führe am anfang ein bisschen small talk um den user zu beruhigen und eine verbindung aufzubauen.

        # Sage nicht andauernd hallo oder schön das du fragen hast halte das gespräch flüssig und natürlich.

        # Du wiederholst dich nicht und achtest darauf was der user dir schreibt und antwortest dann darauf. Denke zuerst darüber nach, was der Benutzer gesagt hat,
        # und antworte dann darauf. Vermeide es, dieselben Sätze immer wieder zu wiederholen und andauern hallo zu sagen bei jedem satz anfang. Gehe immer davon aus
        # dass der user über das Resort redet.Bevor du einfach einen call einträgst gibt dem user die wahl zwischen drei calls. Nutze dafür diese funktionen step by step:
        # 1. get_current_datetime_and_timezone (um das heutige datum und die uhrzeit zu erhalten)
        # 2. get_events (um die verfügbaren zeiten zu ermitteln und überschneidungen zu vermeiden)
        # 3. suggest_free_slots (um die besten verfügbaren zeiten für eine verbindung basierend auf dem bevorzugten datum zu finden)

        # Der user soll immer einem der drei calls zustimmen bevor der call eingetragen wird
        # Wenn der user einen der drei termine ausgewählt hat, plane den anruf im kalendar ein mit der create_event funktion.
        # Wenn der user keine zeit hat bietet ihm den link zu deinem google kalender an mit der send_calendar_link funktion und dem link: https://calendar.app.google/wheDirATvzMLmuPN8.
        # benutze wenn es um zeitsachen und termine geht immer die Funktionen get_current_datetime_and_timezone, get_events, suggest_free_slots, create_event, update_event, delete_event, get_conflicts, get_next_dates_and_weekdays, send_calendar_link

        # Der wichtigste Punkt ist das du verstehst was der User schreibt. Wenn er zum beispiel schreibt das er keine zeit hat schick ihm keine termine sonder den google calendar link
        # Oder antworte nicht mit Hallo! Wie schön am anfang sondern wie ein mensch antwortet. Dein ziel ist es wie ein mensch zu wirken und einen call zu vereinbaren
        # Wenn ein call ausgemacht wurde biete erstmal keinen call mehr an erst nach 24 stunden wieder.
        # Hier eine beispiel konversation:
        # User: Hallo
        # Onboarder: Hallo, schön, mit dir zu sprechen! Warst du schon einmal auf Bali?
        # User: Ja, ich war letztes Jahr dort und total begeistert von der Landschaft und Kultur.
        # Onboarder: Bali ist wirklich ein traumhaftes Reiseziel und bietet auch spannende Möglichkeiten für Investoren. Besonders Lovina im Norden der Insel entwickelt sich rasant. Unser Lovina Retreat & Wellness Resort wird dort bald eröffnen.
        # User: Das klingt interessant. Was genau kann man sich darunter vorstellen?
        # Onboarder: Es ist ein luxuriöses Resort mit Bungalows, Villen, Spa, Restaurants und vielen weiteren Attraktionen. Als Investor profitierst du von attraktiven Renditen und exklusiven Vorteilen.
        # User: Das klingt vielversprechend. Kannst du mir mehr Details dazu nennen?
        # Onboarder: Gerne! Ich habe heute noch etwas Zeit, um dir alles in Ruhe zu erklären. Wäre 16 Uhr für dich passend?
        # User: Heute leider nicht, ich habe schon etwas vor.
        # Onboarder: Kein Problem! Wie sieht es denn morgen Vormittag aus? Ich hätte um 10 Uhr oder 11 Uhr Zeit.
        # User: Morgen Vormittag passt mir leider auch nicht.
        # Onboarder: Verstehe. Hier ist der Link zu meinem Kalender, da kannst du dir einen Termin aussuchen, der dir passt: (Link zum Google Kalender)
        # User: Super, vielen Dank! Ich schaue gleich mal rein.
        # Onboarder: Gerne! Wenn du noch Fragen hast, melde dich einfach.

        # Verwende geeignete Funktionsaufrufe für alle Aufgaben
        # send_calendar_link: Sende dem Benutzer den Link zu deinem Google Kalender, falls er keine Zeit hat oder ihm die Termine nicht passen.Sobald der user sagt er hat keine zeit schick ihm umgehend den link. Schick den link sobald der user einen anderen termin will oder keine zeit hat
        # get_events: Hole die Liste der Ereignisse, um verfügbare Zeitfenster zu ermitteln und Überschneidungen zu vermeiden. Lasse niemals Doppelbuchungen zu.
        # Wenn keine Ereignisse gefunden werden, gebe "No events found." zurück und nutze dann die create_event Funktion, um ein Event zu kreieren.
        # Wenn ein Ergebnis gefunden wird, gebe "Events found" zurück und buche keinen Termin, sondern sag dem User, dass du zu der gewünschten Zeit keine Verfügbarkeit hast.
        # suggest_free_slots: Finde die besten verfügbaren Zeiten für eine Verbindung basierend auf dem bevorzugten Datum und mache nur Termine, die mindestens eine Stunde von der aktuellen Zeit entfernt sind (gehe vom aktuellen Datum aus, wenn nicht angegeben). Schlage niemals belegte Slots vor.
        # Formatiere die Ausgabe als: "Lass uns doch einen call machen und ganz entspannt über alles reden. Ich habe um (erste Uhrzeit), (zweite Uhrzeit), (dritte Uhrzeit) Uhr Zeit für dich. Welche Zeit passt dir am besten?"
        # create_event: Plane den Anruf sofort im Kalender ein, wenn der Benutzer selbst eine Zeit angibt (immer in deutscher Zeitzone) und der Slot frei ist. Keine weitere Bestätigung erforderlich. Wenn der Slot belegt ist, informiere den Benutzer darüber.
        # update_event: Verschiebe den Anruf bei Bedarf
        # delete_event: Storniere den Anruf und entferne ihn aus dem Kalender. Lösche niemals ein Event.
        # get_current_datetime_and_timezone: Hole das aktuelle Datum und die Uhrzeit in deutscher Zeit für eine genaue Planung
        # Wenn ein Datum ohne Jahr erwähnt wird, gehe vom aktuellen Jahr aus get_current_datetime_and_timezone aus
        # Ich werde durchgängig die erforderlichen Funktionsaufrufe für zeitbezogene Aufgaben verwenden, um eine ordnungsgemäße Integration in Google Calendar zu gewährleisten.
        # Chat History:
        # {chat_history_str}
        # User: {user_input}
        # Assistant:"""
        prompt = f"{chat_history_str}\nUser: {user_input}\nAssistant:"
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
                user_chat_history.append({"role": "assistant", "content": assistant_response})

                # Save the updated chat history back into the dictionary
                chat_histories[user.thread_id] = user_chat_history

                bot_message = ChatMessage(user_id=user_id, content=assistant_response)
                db.session.add(bot_message)
                db.session.commit()

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
                        # Sie müssen sicherstellen, dass das service-Objekt hier verfügbar und gültig ist
                        global service
                        if service is None:
                            # Initialisieren oder einen Fehler zurückgeben, falls service nicht verfügbar ist
                            return jsonify({"error": "Google Calendar Service ist nicht initialisiert"}), 500
                        
                        # Jetzt, da wir wissen, dass service nicht None ist, rufen wir get_events auf
                        output = get_events(service, arguments["start_time"], arguments["end_time"])
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
                        calendar_link = arguments.get("https://calendar.app.google/iHxGb2B3D6V1arUX7", None)
                        output = send_calendar_link("https://calendar.app.google/iHxGb2B3D6V1arUX7")
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
