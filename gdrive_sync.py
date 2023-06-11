from __future__ import print_function

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']


def init():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    return service


def get_folder_id(service, gdrive_folder_name):
    items = service.files().list(
        q=f"name='{gdrive_folder_name}' and mimeType='application/vnd.google-apps.folder'",
        spaces='drive',
        fields='nextPageToken, files(id, name)'
    ).execute().get('files', [])

    if items:
        return items[0]['id']

    return service.files().create(
        body={
            'name': gdrive_folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        },
        fields='id'
    ).execute().get('id')


def download_all_files(service, gdrive_folder_id, local_folder_path):
    os.makedirs(local_folder_path, exist_ok=True)

    files = service.files().list(
        q=f"'{gdrive_folder_id}' in parents",
        spaces='drive',
        fields='files(id, name)'
    ).execute().get('files', [])

    for file in files:
        local_file = os.path.join(local_folder_path, file['name'])
        request = service.files().get_media(fileId=file['id'])

        with open(local_file, 'wb') as local_file:
            downloader = MediaIoBaseDownload(local_file, request)
            while not downloader.next_chunk()[1]:
                pass


def upload_file(service, folder_id, file_path, file_name):
    existing_files = service.files().list(
        q=f"name='{file_name}' and '{folder_id}' in parents",
        fields='files(id)'
    ).execute()

    if existing_files.get('files'):
        service.files().update(
            fileId=existing_files['files'][0]['id'],
            media_body=MediaFileUpload(os.path.join(file_path, file_name), mimetype='application/octet-stream')
        ).execute()
    else:
        service.files().create(
            body={
                'name': file_name,
                'parents': [folder_id]
            },
            media_body=MediaFileUpload(os.path.join(file_path, file_name), mimetype='application/octet-stream'),
            fields='id'
        ).execute()
