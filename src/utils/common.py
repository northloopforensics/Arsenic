from datetime import datetime
import os
import logging

def setup_logging(log_file='app.log'):
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def log_message(message):
    logging.info(message)

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
        log_message(f"Created directory: {path}")
    else:
        log_message(f"Directory already exists: {path}")

def get_current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_file(file_path):
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            return file.read()
    else:
        log_message(f"File not found: {file_path}")
        return None

def write_file(file_path, content):
    with open(file_path, 'w') as file:
        file.write(content)
    log_message(f"Wrote to file: {file_path}")