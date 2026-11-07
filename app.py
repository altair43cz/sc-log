from flask import Flask, render_template, Response, request
import os
import re
import time
import json

app = Flask(__name__)


def normalize_html_fragment(content):
    """Convert invalid HTML fragments like <span color=green> into valid CSS spans."""
    if not content:
        return content

    def replace_span(match):
        attrs = (match.group('prefix') or '') + (match.group('suffix') or '')
        color = match.group('color1') or match.group('color2') or match.group('color3') or ''
        if not color:
            return match.group(0)

        attrs = attrs.rstrip()

        style_match = re.search(
            r'\bstyle\s*=\s*(?:"(?P<css1>[^"]*)"|\'(?P<css2>[^\']*)\'|(?P<css3>[^\s>]+))',
            attrs,
            flags=re.IGNORECASE,
        )

        if style_match:
            css_value = style_match.group('css1') or style_match.group('css2') or style_match.group('css3') or ''
            new_css = css_value.rstrip('; ') + '; color: ' + color + ';'
            attrs = attrs[:style_match.start()] + f' style="{new_css}"' + attrs[style_match.end():]
        else:
            attrs = attrs + f' style="color: {color};"'

        return attrs + '>'

    return re.sub(
        r'(?P<prefix><\s*span\b[^>]*?)\s+color\s*=\s*(?:"(?P<color1>[^"]*)"|\'(?P<color2>[^\']*)\'|(?P<color3>[^\s>]+))(?P<suffix>[^>]*)>',
        replace_span,
        content,
        flags=re.IGNORECASE,
    )


def get_stack_mode():
    mode = request.args.get('stacking', request.args.get('st', 'consolidated'))
    mode = (mode or 'consolidated').strip().lower()
    if mode in ('con', 'consolidated'):
        return 'consolidated'
    if mode in ('aln', 'aligned'):
        return 'aligned'
    return 'consolidated'


def should_ignore_name(name):
    return name.startswith('.') or name.endswith('~')


def scan_row_names(data_dir):
    rows = []
    if not os.path.exists(data_dir):
        return rows

    entries = []
    for entry in os.scandir(data_dir):
        if should_ignore_name(entry.name):
            continue
        if entry.is_dir(follow_symlinks=False) and re.match(r'^\d+$', entry.name):
            entries.append(entry.name)

    return sorted(entries, key=lambda value: int(value))


def scan_row_files(dir_path):
    files = []
    if not os.path.exists(dir_path):
        return files

    entries = []
    for entry in os.scandir(dir_path):
        if should_ignore_name(entry.name):
            continue
        if entry.is_file(follow_symlinks=False):
            entries.append(entry.name)

    return sorted(entries)


def read_cell_content(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read().strip()
        return normalize_html_fragment(content)
    except Exception:
        return ''


def get_data_rows(data_dir):
    rows = []
    for row_name in scan_row_names(data_dir):
        dir_path = os.path.join(data_dir, row_name)
        cells = []
        for filename in scan_row_files(dir_path):
            filepath = os.path.join(dir_path, filename)
            cells.append({
                'name': filename,
                'content': read_cell_content(filepath)
            })

        rows.append({
            'name': row_name,
            'cells': cells,
            'cells_by_name': {cell['name']: cell for cell in cells}
        })

    return rows


@app.route('/')
def index():
    data_dir = os.getenv('XDG_RUNTIME_DIR', '/run/user/1000') + '/sc-log'
    rows = get_data_rows(data_dir)
    file_names = []
    for row in rows:
        for cell in row['cells']:
            if cell['name'] not in file_names:
                file_names.append(cell['name'])

    return render_template('table.html', rows=rows, file_names=file_names, stacking=get_stack_mode())


@app.route('/stream')
def stream():
    """Server-Sent Events endpoint for streaming file updates"""
    def generate():
        data_dir = os.getenv('XDG_RUNTIME_DIR', '/run/user/1000') + '/sc-log'

        def snapshot():
            state = {}
            for row in get_data_rows(data_dir):
                state[row['name']] = {
                    cell['name']: cell['content'] for cell in row['cells']
                }
            return state

        local_cache = snapshot()

        yield f"data: {json.dumps({'type': 'init'})}\n\n"

        while True:
            try:
                current = snapshot()

                current_rows = set(current)
                cached_rows = set(local_cache)

                for row_name in sorted(current_rows | cached_rows, key=lambda value: int(value) if re.match(r'^\d+$', value) else 999999):
                    if row_name not in current:
                        local_cache.pop(row_name, None)
                        yield f"data: {json.dumps({'type': 'delete', 'row': row_name, 'file': ''})}\n\n"
                        continue

                    cached_files = set(local_cache.get(row_name, {}))
                    current_files = set(current.get(row_name, {}))

                    for file_name in sorted(current_files | cached_files):
                        old_content = local_cache.get(row_name, {}).get(file_name)
                        new_content = current.get(row_name, {}).get(file_name)

                        if file_name not in current_files:
                            yield f"data: {json.dumps({'type': 'delete', 'row': row_name, 'file': file_name})}\n\n"
                            continue

                        if old_content != new_content:
                            yield f"data: {json.dumps({'type': 'update', 'row': row_name, 'file': file_name, 'content': new_content})}\n\n"

                    local_cache[row_name] = current[row_name]

                time.sleep(0.5)
            except Exception as e:
                print(f"Stream error: {e}")
                break

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


if __name__ == '__main__':
    app.run(debug=True)
