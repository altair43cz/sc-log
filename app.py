from flask import Flask, render_template, Response
import os
import re
import time
import json

app = Flask(__name__)


@app.route('/')
def index():
    # Get all files in current directory with numeric names
    files = []
    # Use the directory where this script is located
    data_dir = os.getenv('XDG_RUNTIME_DIR', '/run/user/1000') + \
        '/sc-log'

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


@app.route('/stream')
def stream():
    """Server-Sent Events endpoint for streaming file updates"""
    def generate():
        data_dir = os.getenv('XDG_RUNTIME_DIR', '/run/user/1000') + \
            '/sc-log'

        # Initialize cache with current state
        local_cache = {}
        if os.path.exists(data_dir):
            for filename in sorted(os.listdir(data_dir)):
                filepath = os.path.join(data_dir, filename)
                if os.path.isfile(filepath) and re.match(r'^\d+$', filename):
                    current_content = get_last_line(filepath)
                    local_cache[filename] = current_content

        # Send initial state
        yield f"data: {json.dumps({'type': 'init'})}\n\n"

        while True:
            try:
                if os.path.exists(data_dir):
                    for filename in sorted(os.listdir(data_dir)):
                        filepath = os.path.join(data_dir, filename)
                        if os.path.isfile(filepath) and re.match(r'^\d+$', filename):
                            current_content = get_last_line(filepath)

                            # Check if content changed
                            if filename not in local_cache or local_cache[filename] != current_content:
                                local_cache[filename] = current_content
                                # Send update
                                data = {
                                    'type': 'update',
                                    'file': filename,
                                    'content': current_content
                                }
                                yield f"data: {json.dumps(data)}\n\n"

                time.sleep(0.5)  # Check every 500ms
            except Exception as e:
                print(f"Stream error: {e}")
                break

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


if __name__ == '__main__':
    app.run(debug=True)
