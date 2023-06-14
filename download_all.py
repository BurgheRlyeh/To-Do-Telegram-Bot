import gdrive_sync

if __name__ == '__main__':
    service = gdrive_sync.init()
    folder_id = gdrive_sync.get_folder_id(service, 'todo_telegram_bot_users')
    gdrive_sync.download_all_files(service, folder_id, 'users')
