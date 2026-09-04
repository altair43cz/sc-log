from flask import Flask, render_template, Response
import os
import re
import threading
import time
import json

app = Flask(__name__)

# Store file contents to detect changes
file_cache = {}
cache_lock = threading.Lock()

@app.route('/')
def index():
    # Get all files in current directory with numeric names
    files = []
    # Use the directory where this script is located
    app_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(app_dir, 'dat')
    
    if os.path.exists(data_dir):
        for filename in os.listdir(data_dir):
            filepath = os.path.join(data_dir, filename)
            if os.path.isfile(filepath) and re.match(r'^\d+$', filename):
                files.append({'name': filename})
    
    # Sort by numeric value
    files.sort(key=lambda x: int(x['name']))
    
    return render_template('table.html', files=files)

def get_last_line(filepath):
    """Get the last line of a file"""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            return lines[-1].strip() if lines else ""
    except:
        return ""

def file_watcher():
    """Background thread that monitors files for changes"""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(app_dir, 'dat')
    
    while True:
        try:
            if os.path.exists(data_dir):
                for filename in sorted(os.listdir(data_dir)):
                    filepath = os.path.join(data_dir, filename)
                    if os.path.isfile(filepath) and re.match(r'^\d+$', filename):
                        current_content = get_last_line(filepath)
                        
                        with cache_lock:
                            if filename not in file_cache or file_cache[filename] != current_content:
                                file_cache[filename] = current_content
        except:
            pass
        
        time.sleep(0.5)  # Check every 500ms

@app.route('/stream')
def stream():
    """Server-Sent Events endpoint for streaming file updates"""
    def generate():
        # Send initial state
        yield f"data: {json.dumps({'type': 'init'})}\n\n"
        
        while True:
            try:
                app_dir = os.path.dirname(os.path.abspath(__file__))
                data_dir = os.path.join(app_dir, 'dat')
                
                if os.path.exists(data_dir):
                    for filename in sorted(os.listdir(data_dir)):
                        filepath = os.path.join(data_dir, filename)
                        if os.path.isfile(filepath) and re.match(r'^\d+$', filename):
                            current_content = get_last_line(filepath)
                            
                            with cache_lock:
                                if filename not in file_cache or file_cache[filename] != current_content:
                                    file_cache[filename] = current_content
                                    # Send update
                                    data = {
                                        'type': 'update',
                                        'file': filename,
                                        'content': current_content
                                    }
                                    yield f"data: {json.dumps(data)}\n\n"
                
                time.sleep(0.5)  # Check every 500ms
            except:
                pass
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    # Start background file watcher thread
    watcher_thread = threading.Thread(target=file_watcher, daemon=True)
    watcher_thread.start()
    
    app.run(debug=True)
