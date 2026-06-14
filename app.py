from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import glob
import threading
app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

progress_status = {"percentage": "0%", "status": "Idle"}

def ydl_progress_hook(d):
    if d['status'] == 'downloading':
        pct = d.get('_percent_str', '0%').strip()
        clean_pct = ''.join(c for c in pct if c.isdigit() or c == '.')
        progress_status["percentage"] = f"{clean_pct}%" if clean_pct else "0%"
        progress_status["status"] = f"Downloading: {progress_status['percentage']}"
    elif d['status'] == 'finished':
        progress_status["percentage"] = "100%"
        progress_status["status"] = "Processing files..."

@app.route('/progress', methods=['GET'])
def get_progress():
    return jsonify(progress_status)

# Feature 1 Fix: Pulls video information and thumbnail dynamically without downloading
@app.route('/fetch-metadata', methods=['POST'])
def fetch_metadata():
    data = request.json
    video_url = data.get('url')
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        with yt_dlp.YoutubeDL({'skip_download': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return jsonify({
                "title": info.get('title', 'Unknown Title'),
                "thumbnail": info.get('thumbnail', '')
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Feature 2 Fix: Uses Windows native os.startfile to directly pop open your folder frame
@app.route('/open-folder', methods=['POST'])
def open_downloads_folder():
    try:
        os.startfile(os.path.abspath(DOWNLOAD_DIR))
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/download', methods=['POST'])
def download_media():
    global progress_status
    data = request.json
    video_url = data.get('url')
    mode_type = data.get('mode')
    quality_target = data.get('quality')

    if not video_url:
        return jsonify({"error": "No URL specified"}), 400

    progress_status = {"percentage": "0%", "status": "Initializing download configurations..."}

    # REMOVED the old loop that was wiping out your previous files here.
    # Videos will now save sequentially without replacing old ones!

    if mode_type == 'audio':
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'ffmpeg_location': os.getcwd(),
            'progress_hooks': [ydl_progress_hook],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        height_map = {'320': '320', '480': '480', '720': '720', '1080': '1080', '4k': '2160'}
        max_height = height_map.get(quality_target, '1080')
        fmt_string = f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={max_height}]+bestaudio/best"
        
        ydl_opts = {
            'format': fmt_string,
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'ffmpeg_location': os.getcwd(),
            'merge_output_format': 'mp4',
            'progress_hooks': [ydl_progress_hook],
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)
            
            if mode_type == 'video':
                filename = os.path.splitext(filename)[0] + ".mp4"
            else:
                filename = os.path.splitext(filename)[0] + ".mp3"

        progress_status = {"percentage": "100%", "status": "Ready"}
        return send_file(filename, as_attachment=True)

    except Exception as e:
        progress_status = {"percentage": "0%", "status": f"Error: {str(e)}"}
        return jsonify({"error": str(e)}), 500

def run_flask_backend():
    app.run(port=5000, debug=False, threaded=True)

if __name__ == '__main__':
    backend_thread = threading.Thread(target=run_flask_backend, daemon=True)
    backend_thread.start()

    import webview
    webview.create_window(
        title="STARVEL Downloader", 
        url=os.path.join(os.getcwd(), "index.html"),
        width=950,
        height=750,
        resizable=True
    )
    webview.start()
