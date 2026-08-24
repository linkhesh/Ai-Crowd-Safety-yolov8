import os
import cv2
import time
import threading
import numpy as np
import requests
import json
from flask import Flask, Response, request, jsonify
from ultralytics import YOLO
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = os.path.abspath('uploads')
CONFIG_FILE = os.path.abspath('config.json')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------- CONFIGURATION -------- #
MODEL_PATH = "C:/Users/ACER/OneDrive/Desktop/dashboardpy/best.pt"

model_lock = threading.Lock()

try:
    model = YOLO(MODEL_PATH)
    print("Custom model loaded successfully from:", MODEL_PATH)
except Exception as e:
    print(f"Custom model not found at {MODEL_PATH}, using default. Error: {e}")
    model = YOLO("yolov8n.pt")

# -------- DYNAMIC STATE MANAGEMENT -------- #
# Default configuration
global_config = {
    "sms_phones": [], 
    "num_zones": 4,   
    "num_cams": 4     
}

# Load configuration from JSON file if it exists
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            saved_config = json.load(f)
            global_config.update(saved_config)
    except Exception as e:
        print(f"Error loading config file: {e}")

def save_config():
    """Saves the current global_config to a JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(global_config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

zones = {}
streamers = {}

def get_error_frame(text):
    err_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(err_frame, text, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    return err_frame

# -------- TELEGRAM BOT INTEGRATION -------- #
def send_sms(chat_id, message):
    if not chat_id: return
    print(f"\n[TELEGRAM TRIGGERED] To Chat ID: {chat_id} | Message: {message}")
    
    # PASTE YOUR BOTFATHER TOKEN HERE
    bot_token = '8481898940:AAGREQm-Am_MMqaK73sCYpUuvcopKIV-v9E'
    # ---------------------------------
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        response = requests.post(url, json={
            'chat_id': chat_id,
            'text': message
        })
        print(f"Telegram API Response (ID: {chat_id}):", response.json(), "\n")
    except Exception as e:
        print("Telegram Error:", e, "\n")

# -------- ISOLATED BACKGROUND THREADS FOR EACH CAMERA -------- #
class VideoStreamer:
    def __init__(self, zone_id):
        self.zone_id = zone_id
        self.source = zones[zone_id]['source']
        self.cap = None
        self.frame = get_error_frame("INITIALIZING...")
        self.frame_lock = threading.Lock()
        self.running = True  
        
        threading.Thread(target=self.update, daemon=True).start()

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

    def update(self):
        while self.running:
            current_source = zones[self.zone_id]['source']
            if current_source != self.source or self.cap is None:
                if self.cap: 
                    self.cap.release()
                self.source = current_source
                if self.source != -1:
                    self.cap = cv2.VideoCapture(self.source)
                else:
                    self.cap = None

            if self.source == -1 or self.cap is None:
                with self.frame_lock:
                    self.frame = get_error_frame("NO CAMERA ASSIGNED")
                zones[self.zone_id]['count'] = 0
                zones[self.zone_id]['status'] = "NORMAL"
                time.sleep(0.5)
                continue

            ret, img = self.cap.read()

            if not ret:
                if isinstance(self.source, str):
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.source)
                    ret, img = self.cap.read()
                    if not ret:
                        with self.frame_lock: self.frame = get_error_frame("FILE ERROR")
                        zones[self.zone_id]['count'] = 0
                        zones[self.zone_id]['status'] = "NORMAL"
                        time.sleep(1)
                else:
                    with self.frame_lock: self.frame = get_error_frame(f"CAM {self.source} UNAVAILABLE")
                    zones[self.zone_id]['count'] = 0
                    zones[self.zone_id]['status'] = "NORMAL"
                    self.cap.release()
                    time.sleep(1)
                    self.cap = cv2.VideoCapture(self.source)
                continue

            if ret and img is not None:
                with model_lock:
                    results = model(img, verbose=False, conf=0.4)[0]
                
                count = len(results.boxes)
                zones[self.zone_id]['count'] = count
                thresh = zones[self.zone_id]['threshold']
                
                if count >= thresh:
                    status, color = "DANGER", (0, 0, 255)
                    curr_time = time.time()
                    
                    if curr_time - zones[self.zone_id]['last_sms'] > 10:
                        for chat_id in global_config['sms_phones']:
                            threading.Thread(target=send_sms, args=(chat_id, f"ALARM: {self.zone_id.upper()} OVERCROWDED! Count: {count}")).start()
                        
                        zones[self.zone_id]['last_sms'] = curr_time
                elif count >= (thresh - 5) and (thresh - 5) > 0:
                    status, color = "WARNING", (0, 255, 255)
                else:
                    status, color = "NORMAL", (0, 255, 0)
                
                zones[self.zone_id]['status'] = status

                for box in results.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(img, (x1,y1), (x2,y2), color, 2)
                
                cv2.putText(img, f"{status} | Count: {count}", (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                with self.frame_lock:
                    self.frame = img.copy()

                if isinstance(self.source, str):
                    time.sleep(0.03)

    def get_frame(self):
        with self.frame_lock:
            return self.frame.copy()

def setup_system():
    global zones, streamers
    num_zones = global_config['num_zones']
    target_zone_ids = [f"zone{i}" for i in range(1, num_zones + 1)]
    current_zone_ids = list(zones.keys())

    for zid in current_zone_ids:
        if zid not in target_zone_ids:
            if zid in streamers:
                streamers[zid].stop()
                del streamers[zid]
            del zones[zid]

    for i, zid in enumerate(target_zone_ids):
        if zid not in zones:
            default_source = i if i < global_config['num_cams'] else -1
            zones[zid] = {"threshold": 20, "count": 0, "status": "NORMAL", "source": default_source, "last_sms": 0}
            streamers[zid] = VideoStreamer(zid)

setup_system()

# -------- HTML HMI INTERFACE -------- #
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>INDUSTRIAL CROWD HMI v17</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; overflow: hidden; }
        .sidebar { background: #161b22; height: 100vh; border-right: 2px solid #30363d; padding: 20px; width: 380px; position: fixed; overflow-y: auto; }
        .main-content { margin-left: 380px; padding: 20px; height: 100vh; overflow-y: auto; }
        .video-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 10px; }
        .video-box { border: 1px solid #30363d; background: #000; position: relative; min-height: 250px; border-radius: 4px; }
        .zone-tag { position: absolute; top: 5px; left: 10px; background: rgba(0,0,0,0.7); padding: 2px 8px; font-size: 0.8rem; z-index: 5; }
        .control-group { background: #1c2128; border: 1px solid #444c56; padding: 12px; border-radius: 6px; margin-bottom: 15px; }
        .status-DANGER { border-left: 6px solid #f85149; background: rgba(248, 81, 73, 0.05); }
        .status-WARNING { border-left: 6px solid #d29922; }
        .status-NORMAL { border-left: 6px solid #238636; }
        .alarm-text { color: #f85149; font-weight: bold; font-size: 0.9rem; animation: blinker 1.5s linear infinite; }
        @keyframes blinker { 50% { opacity: 0.5; } }
        .nav-tabs .nav-link.active { background-color: #21262d !important; color: #fff !important; border-color: #30363d !important; border-bottom-color: transparent !important;}
        .log-entry { border-bottom: 1px solid #30363d; padding: 4px 0; }
        .contact-entry { background: #21262d; border: 1px solid #30363d; padding: 5px 10px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h5 class="text-info mb-3">HMI CONTROL PANEL</h5>
        
        <div class="mb-3 p-2" style="background: #1c2128; border-radius: 6px; border: 1px solid #444c56;">
            <label class="small text-warning mb-1">System Setup</label>
            <div class="d-flex gap-2">
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-dark text-white border-secondary">Zones</span>
                    <input type="number" id="sys-zones" class="form-control bg-dark text-white border-secondary" min="1" max="16">
                </div>
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-dark text-white border-secondary">Cams</span>
                    <input type="number" id="sys-cams" class="form-control bg-dark text-white border-secondary" min="1" max="16">
                </div>
            </div>
            <button class="btn btn-outline-warning w-100 btn-sm mt-2" onclick="applySystemSetup()">Apply & Restart UI</button>
        </div>

        <div class="mb-3 p-2" style="background: #1c2128; border-radius: 6px; border: 1px solid #444c56;">
            <label class="small text-muted mb-1">Telegram Contacts (Chat IDs)</label>
            <div class="input-group input-group-sm mb-2">
                <input type="text" id="contact-input" class="form-control bg-dark text-white border-secondary" placeholder="e.g. 5123456789">
                <button class="btn btn-outline-info" onclick="addContact()">Add ID</button>
            </div>
            <div id="contacts-list" style="max-height: 120px; overflow-y: auto; font-size: 0.85rem;">
                </div>
        </div>

        <ul class="nav nav-tabs border-secondary mb-2" id="myTab" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active bg-dark text-danger border-secondary py-1" data-bs-toggle="tab" data-bs-target="#active-alarms" type="button">Active Alarms</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link bg-dark text-info border-secondary py-1" data-bs-toggle="tab" data-bs-target="#history-logs" type="button">Logs</button>
          </li>
        </ul>
        
        <div class="tab-content mb-3" id="myTabContent" style="min-height: 80px; background: #21262d; border: 1px solid #30363d; border-radius: 0 6px 6px 6px; padding: 10px;">
          <div class="tab-pane fade show active" id="active-alarms">
            <div id="alarm-dashboard"><span class="text-muted small">No active alarms</span></div>
          </div>
          <div class="tab-pane fade" id="history-logs">
            <div id="log-dashboard" style="max-height: 120px; overflow-y: auto; font-size: 0.8rem; color: #8b949e;">
                <span class="text-muted small">No history yet.</span>
            </div>
          </div>
        </div>

        <div id="zone-controls"></div>
    </div>
    
    <div class="main-content">
        <div class="video-grid" id="video-grid">
            </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let zoneKeys = [];
        let prevStatus = {};
        let hasLogs = false;
        let numCams = 4;

        async function init() {
            const res = await fetch('/get_config');
            const conf = await res.json();
            
            document.getElementById('sys-zones').value = conf.num_zones;
            document.getElementById('sys-cams').value = conf.num_cams;
            numCams = conf.num_cams;
            
            // Render the saved contacts
            renderContacts(conf.sms_phones);

            zoneKeys = Array.from({length: conf.num_zones}, (_, i) => `zone${i+1}`);
            
            const controlContainer = document.getElementById('zone-controls');
            const videoContainer = document.getElementById('video-grid');
            
            controlContainer.innerHTML = "";
            videoContainer.innerHTML = "";

            zoneKeys.forEach(z => {
                prevStatus[z] = "NORMAL";

                let camButtons = "";
                for(let c=0; c<numCams; c++) {
                    camButtons += `<button class="btn btn-dark btn-sm border-secondary mb-1" onclick="setSource('${z}', ${c})">Cam ${c+1}</button>`;
                }

                controlContainer.innerHTML += `
                    <div id="ctrl-${z}" class="control-group status-NORMAL">
                        <div class="d-flex justify-content-between"><strong>${z.toUpperCase()}</strong> <span id="val-${z}">20</span></div>
                        <input type="range" class="form-range" min="0" max="100" value="20" oninput="updateThresh('${z}', this.value)">
                        <div class="mt-2 btn-group w-100 d-flex flex-wrap">
                            ${camButtons}
                        </div>
                        <div class="mt-2 text-muted small text-center" id="upload-status-${z}"></div>
                        <div class="d-flex align-items-center mt-1">
                            <input type="file" id="file-${z}" class="form-control form-control-sm bg-dark text-white border-secondary" onchange="uploadFile('${z}')">
                            <button class="btn btn-danger btn-sm ms-1 border-secondary" onclick="removeFile('${z}')" title="Remove File">X</button>
                        </div>
                        <div class="mt-1 small text-center text-info" id="count-${z}">Count: 0</div>
                    </div>`;
                
                videoContainer.innerHTML += `
                    <div class="video-box"><span class="zone-tag">${z.toUpperCase()}</span><img src="/stream/${z}" style="width:100%"></div>
                `;
            });
        }

        function renderContacts(phonesArray) {
            const list = document.getElementById('contacts-list');
            list.innerHTML = "";
            if(phonesArray.length === 0) {
                list.innerHTML = '<span class="text-muted small">No contacts saved.</span>';
                return;
            }
            phonesArray.forEach(id => {
                list.innerHTML += `
                    <div class="contact-entry">
                        <span class="text-info">ID: ${id}</span>
                        <button class="btn btn-sm btn-outline-danger" style="padding: 0 5px;" onclick="removeContact('${id}')">X</button>
                    </div>
                `;
            });
        }

        function addContact() {
            const input = document.getElementById('contact-input');
            const val = input.value.trim();
            if(!val) return;
            fetch('/manage_contacts', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'add', chat_id: val})
            }).then(r => r.json()).then(data => {
                input.value = "";
                renderContacts(data.phones);
            });
        }

        function removeContact(val) {
            fetch('/manage_contacts', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'remove', chat_id: val})
            }).then(r => r.json()).then(data => {
                renderContacts(data.phones);
            });
        }

        function applySystemSetup() {
            const z = document.getElementById('sys-zones').value;
            const c = document.getElementById('sys-cams').value;
            fetch('/update_setup', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify({num_zones: z, num_cams: c})
            }).then(() => location.reload());
        }

        function updateThresh(id, val) {
            document.getElementById('val-'+id).innerText = val;
            fetch('/update_config', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, threshold: val})});
        }

        function setSource(id, src) {
            fetch('/set_source', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id, source: src})});
        }

        async function uploadFile(zoneId) {
            const fileInput = document.getElementById('file-'+zoneId);
            const statusText = document.getElementById('upload-status-'+zoneId);
            if (!fileInput.files[0]) return;
            
            statusText.innerText = "Loading video...";
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('id', zoneId);
            
            const response = await fetch('/upload_video', { method: 'POST', body: formData });
            if(response.ok) {
                statusText.innerText = "Active!";
                statusText.className = "mt-2 small text-center text-success";
                setTimeout(() => statusText.innerText = "", 3000);
            }
        }

        function removeFile(zoneId) {
            document.getElementById('file-'+zoneId).value = ""; 
            const statusText = document.getElementById('upload-status-'+zoneId);
            statusText.innerText = "File removed";
            statusText.className = "mt-2 small text-center text-warning";
            setSource(zoneId, -1);
            setTimeout(() => { statusText.innerText = ""; }, 3000);
        }

        setInterval(() => {
            if(zoneKeys.length === 0) return; 
            fetch('/get_stats').then(r => r.json()).then(data => {
                let alarmHTML = "";
                
                zoneKeys.forEach(z => {
                    if(!data[z]) return; 
                    const status = data[z].status;
                    const count = data[z].count;
                    
                    document.getElementById('ctrl-'+z).className = 'control-group status-' + status;
                    document.getElementById('count-'+z).innerText = 'Count: ' + count;
                    
                    if(status === 'DANGER') {
                        alarmHTML += `<div class="alarm-text">${z.toUpperCase()} OVERCROWDED (Count: ${count})</div>`;
                    }

                    if (status === 'DANGER' && prevStatus[z] !== 'DANGER') {
                        try {
                            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                            const oscillator = audioCtx.createOscillator();
                            oscillator.type = 'square';
                            oscillator.frequency.setValueAtTime(440, audioCtx.currentTime); 
                            oscillator.connect(audioCtx.destination);
                            oscillator.start();
                            setTimeout(() => oscillator.stop(), 300); 
                        } catch(e) { }

                        const time = new Date().toLocaleTimeString();
                        const logBox = document.getElementById('log-dashboard');
                        if(!hasLogs) { logBox.innerHTML = ""; hasLogs = true; }
                        logBox.innerHTML = `<div class="log-entry text-warning">[${time}] ${z.toUpperCase()} triggered. Peak: ${count}</div>` + logBox.innerHTML;
                    }
                    
                    prevStatus[z] = status;
                });

                const alarmBox = document.getElementById('alarm-dashboard');
                if (alarmHTML === "") {
                    alarmBox.innerHTML = '<span class="text-muted small">No active alarms</span>';
                } else {
                    alarmBox.innerHTML = alarmHTML;
                }
            }).catch(e => console.log("Waiting for backend..."));
        }, 1000);

        init();
    </script>
</body>
</html>
"""

# -------- BACKEND ROUTES -------- #

@app.route('/stream/<zone_id>')
def stream(zone_id):
    if zone_id not in streamers: return "Zone not initialized", 404
    def generate():
        while zone_id in streamers and streamers[zone_id].running:
            frame = streamers[zone_id].get_frame()
            _, buffer = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.05) 
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/upload_video', methods=['POST'])
def upload_video():
    if 'file' not in request.files: return jsonify(success=False)
    file = request.files['file']
    zone_id = request.form['id']
    if file and file.filename and zone_id in zones:
        filename = secure_filename(file.filename)
        filepath = os.path.abspath(os.path.join(UPLOAD_FOLDER, filename))
        file.save(filepath)
        zones[zone_id]['source'] = filepath
        return jsonify(success=True)
    return jsonify(success=False)

@app.route('/set_source', methods=['POST'])
def set_source():
    d = request.json
    new_source = int(d['source'])
    target_zone = d['id']
    needs_sleep = False
    for z, data in zones.items():
        if z != target_zone and data['source'] == new_source and new_source != -1:
            zones[z]['source'] = -1 
            needs_sleep = True
    if needs_sleep: time.sleep(0.5) 
    if target_zone in zones: zones[target_zone]['source'] = new_source
    return jsonify(success=True)

@app.route('/')
def index(): return HTML_TEMPLATE

@app.route('/get_stats')
def get_stats(): return jsonify(zones)

@app.route('/get_config')
def get_config(): return jsonify(global_config)

@app.route('/update_setup', methods=['POST'])
def update_setup():
    d = request.json
    global_config['num_zones'] = int(d['num_zones'])
    global_config['num_cams'] = int(d['num_cams'])
    save_config()  # Save changes to disk
    setup_system()
    return jsonify(success=True)

@app.route('/update_config', methods=['POST'])
def update_config():
    d = request.json
    if d['id'] in zones: zones[d['id']]['threshold'] = int(d['threshold'])
    return jsonify(success=True)

@app.route('/manage_contacts', methods=['POST'])
def manage_contacts():
    d = request.json
    action = d.get('action')
    chat_id = str(d.get('chat_id', '')).strip()
    
    if chat_id:
        if action == 'add' and chat_id not in global_config['sms_phones']:
            global_config['sms_phones'].append(chat_id)
            save_config()  # Save new contact to disk
        elif action == 'remove' and chat_id in global_config['sms_phones']:
            global_config['sms_phones'].remove(chat_id)
            save_config()  # Save removal to disk
            
    return jsonify(success=True, phones=global_config['sms_phones'])

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)