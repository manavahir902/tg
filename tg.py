import os
import sys
import pickle
import sqlite3
from telethon.sync import TelegramClient
from telethon.errors.rpcerrorlist import PhoneNumberOccupiedError, SessionPasswordNeededError
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.functions.messages import SendMessageRequest, DeleteHistoryRequest, GetDialogsRequest
from telethon.tl.functions.contacts import DeleteContactsRequest, GetContactsRequest
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.tl.types import InputPeerChannel, InputPeerChat, InputPeerUser, Channel, Chat, User

# Function to load API ID and Hash from info.pkl
def load_api_info():
    try:
        with open('info.pkl', 'rb') as f:
            api_info = pickle.load(f)
            api_id = api_info['api_id']
            api_hash = api_info['api_hash']
            return api_id, api_hash
    except FileNotFoundError:
        print('Error: info.pkl file not found. Please create the file with API ID and Hash.')
        sys.exit(1)
    except Exception as e:
        print(f'Error loading API info: {e}')
        sys.exit(1)

# Function to handle login process
def login(phone, session_name, api_id, api_hash):
    client = TelegramClient(session_name, api_id, api_hash)
    client.connect()

    if not client.is_user_authorized():
        try:
            client.send_code_request(phone)
            while True:
                code = input('Enter the code you received: ')
                try:
                    client.sign_in(phone, code)
                    break
                except PhoneCodeInvalidError:
                    print('Incorrect code. Please try again.')
        except PhoneNumberOccupiedError:
            print('Phone number is already in use.')
        except SessionPasswordNeededError:
            password = input('Two-step verification is enabled. Please enter your password: ')
            client.sign_in(password=password)
    
    if client.is_user_authorized():
        print('Login successful!')
    else:
        print('Login failed! Please check your phone number and try again.')
    
    return client

# Function to send a message to a bot
def send_message(client, username, message):
    try:
        client(SendMessageRequest(username, message))
        print('Message sent successfully!')
    except Exception as e:
        print(f'Failed to send message: {e}')

# Function to clean up sessions
def clean_up(client):
    try:
        # Fetch all dialogs
        result = client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=client.get_input_entity('me'),
            limit=100,
            hash=0
        ))

        dialogs = result.dialogs
        for dialog in dialogs:
            entity = client.get_entity(dialog.peer)
            if isinstance(entity, (Channel, Chat)):
                print(f'Leaving channel/group: {entity.title}')
                client(LeaveChannelRequest(entity))
            if isinstance(entity, (Channel, Chat, User)):
                print(f'Deleting history: {entity.title if hasattr(entity, "title") else entity.username}')
                client(DeleteHistoryRequest(peer=entity, just_clear=False, revoke=True, max_id=0))

        # Deleting all synced contacts
        contacts = client(GetContactsRequest(hash=0)).users
        contact_ids = [contact.id for contact in contacts]
        if contact_ids:
            client(DeleteContactsRequest(id=contact_ids))
        
        print('Clean up successful!')
    except Exception as e:
        print(f'Failed to clean up: {e}')

# Function to check and exit all channels, groups, and delete all chats
def check_and_exit_channels(client):
    try:
        # Fetch all dialogs
        result = client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=client.get_input_entity('me'),
            limit=100,
            hash=0
        ))

        dialogs = result.dialogs
        channels_or_groups_found = False

        for dialog in dialogs:
            entity = client.get_entity(dialog.peer)
            if isinstance(entity, (Channel, Chat)):
                channels_or_groups_found = True
                break

        if channels_or_groups_found:
            for dialog in dialogs:
                entity = client.get_entity(dialog.peer)
                if isinstance(entity, (Channel, Chat)):
                    print(f'Exiting channel/group: {entity.title}')
                    client(LeaveChannelRequest(entity))
                if isinstance(entity, User):
                    try:
                        print(f'Deleting chat: {entity.username}')
                        client(DeleteHistoryRequest(peer=entity, just_clear=False, max_id=0))
                    except Exception as e:
                        print(f'Failed to delete history for {entity.username}: {e}')
            print('Exited all channels and groups and deleted all chats.')
        else:
            print('No channels, groups, or chats found.')

    except Exception as e:
        print(f'Failed to check and delete: {e}')

# Function to terminate all other sessions except the current one
def terminate_other_sessions(client, phone):
    try:
        authorizations = client(GetAuthorizationsRequest()).authorizations

        for authorization in authorizations:
            if authorization.current:
                current_hash = authorization.hash
                break
        else:
            print('Current session not found in authorizations.')
            return

        for authorization in authorizations:
            if authorization.hash != current_hash:
                print(f'Terminating session: {authorization.hash}')
                client(ResetAuthorizationRequest(hash=authorization.hash))
        
        print('Terminated all other sessions successfully!')
        with open('new_number.txt', 'a') as file:
            file.write(f'{phone}\n')
    except Exception as e:
        if "current session is too new" in str(e):
            print(f'Failed to terminate other sessions: {e}')
            with open('old_number.txt', 'a') as file:
                file.write(f'{phone}\n')
        else:
            print(f'Failed to terminate other sessions: {e}')
            with open('old_number.txt', 'a') as file:
                file.write(f'{phone}\n')

# Function to handle main menu and user choices
def main_menu():
    while True:
        print('Enter 1 to start the login process and save session file:')
        print('Enter 2 to start the login process and save session in new folder:')
        print('Enter 3 to send a message to @FastReciver_bot using the session from choice 1:')
        print('Enter 4 to clean up sessions in the "sessions" folder:')
        print('Enter 5 to check if the number has joined any channels and exit them if found:')
        print('Enter 6 to start the login process, save session, and terminate all other sessions except the current one (repeatable):')
        choice = input('Enter your choice (or q to quit): ')

        if choice == 'q':
            print('Exiting...')
            break

        phone = None
        client = None

        try:
            if choice == '1':
                phone = input('Enter your phone number (with country code): ')
                api_id, api_hash = load_api_info()
                client = login(phone, 'session', api_id, api_hash)
            elif choice == '2':
                phone = input('Enter your phone number (with country code): ')
                session_folder = 'sessions'
                os.makedirs(session_folder, exist_ok=True)
                session_name = os.path.join(session_folder, f'session_{phone}')
                api_id, api_hash = load_api_info()
                client = login(phone, session_name, api_id, api_hash)
            elif choice == '3':
                api_id, api_hash = load_api_info()
                if os.path.exists('session.session'):
                    client = TelegramClient('session', api_id, api_hash)
                    client.connect()
                    if not client.is_user_authorized():
                        print('Client is not authorized. Please login using choice 1 first.')
                        continue
                    send_message(client, '@FastReciver_bot', 'Hello from Termux!')
                    client.disconnect()
                else:
                    print('No session found. Please login using choice 1 first.')
            elif choice == '4':
                api_id, api_hash = load_api_info()
                session_folder = 'sessions'
                if os.path.exists(session_folder):
                    for session_file in os.listdir(session_folder):
                        if session_file.endswith('.session'):
                            session_name = os.path.join(session_folder, session_file)
                            try:
                                client = TelegramClient(session_name, api_id, api_hash)
                                client.connect()
                                if client.is_user_authorized():
                                    clean_up(client)
                                else:
                                    print(f'Session {session_name} is not authorized.')
                                client.disconnect()
                            except sqlite3.OperationalError as e:
                                print(f'Failed to access session {session_name}: {e}')
                            finally:
                                if client:
                                    client.disconnect()
                else:
                    print(f'No sessions found in the folder "{session_folder}".')
            elif choice == '5':
                api_id, api_hash = load_api_info()
                session_folder = 'sessions'
                if os.path.exists(session_folder):
                    for session_file in os.listdir(session_folder):
                        if session_file.endswith('.session'):
                            session_name = os.path.join(session_folder, session_file)
                            try:
                                client = TelegramClient(session_name, api_id, api_hash)
                                client.connect()
                                if client.is_user_authorized():
                                    check_and_exit_channels(client)
                                else:
                                    print(f'Session {session_name} is not authorized.')
                                client.disconnect()
                            except sqlite3.OperationalError as e:
                                print(f'Failed to access session {session_name}: {e}')
                            finally:
                                if client:
                                    client.disconnect()
                else:
                    print(f'No sessions found in the folder "{session_folder}".')
            elif choice == '6':
                api_id, api_hash = load_api_info()
                session_folder = 'sessions'
                os.makedirs(session_folder, exist_ok=True)
                
                while True:
                    phone = input('Enter your phone number (with country code) (or q to quit): ')
                    if phone == 'q':
                        break
                    session_name = os.path.join(session_folder, f'session_{phone}')
                    client = login(phone, session_name, api_id, api_hash)
                    if client and client.is_user_authorized():
                        terminate_other_sessions(client, phone)
                    client.disconnect()
            else:
                print('Invalid choice!')
        except NameError:
            print('API ID and Hash not loaded. Please choose option 1 or 2 first.')
        except Exception as e:
            print(f'Error: {e}')
        finally:
            # Ensure the client disconnects in case of any exceptions
            if client:
                client.disconnect()

if __name__ == '__main__':
    main_menu()

