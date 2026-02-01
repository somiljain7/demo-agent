from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from livekit import api
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="LiveKit AI Voice Agent API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Configuration - NEVER hard-code these, always use environment variables
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Validate configuration
if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
    raise ValueError("Missing required environment variables. Please set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET")


class JoinRequest(BaseModel):
    room_name: str
    participant_name: str
    metadata: dict = {}


class TokenResponse(BaseModel):
    token: str
    url: str
    room_name: str


class KnowledgeBaseRequest(BaseModel):
    website_url: str
    max_pages: int = 50


@app.get("/")
def root():
    return {
        "service": "LiveKit AI Voice Agent",
        "status": "running",
        "components": {
            "stt": "Deepgram",
            "llm": "Groq (Llama 3.3 70B)",
            "tts": "Cartesia"
        },
        "endpoints": {
            "token": "/token",
            "demo": "/demo",
            "extract_kb": "/extract-knowledge-base"
        }
    }


@app.get("/bg.gif")
async def get_background():
    return FileResponse("bg.gif")


@app.post("/token", response_model=TokenResponse)
async def create_token(request: JoinRequest):
    """Create access token for participant to join room"""
    try:
        # Update room metadata if provided
        if request.metadata:
            import json
            lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            meta_json = json.dumps(request.metadata)
            
            try:
                # Strategy: Try to create room first (ensures it exists and sets metadata)
                # If it exists, this might fail or return the existing room (depending on API version).
                # To be safe, we wrap in try/except and fallback to update.
                print(f"Attempting to set metadata for room: {request.room_name}")
                
                try:
                    await lkapi.room.create_room(api.CreateRoomRequest(
                        name=request.room_name,
                        metadata=meta_json,
                        empty_timeout=10 * 60, # Keep alive for 10 mins if empty
                    ))
                    print(f"Created room '{request.room_name}' with metadata.")
                except Exception as create_err:
                    # If creation failed, assume it exists and try to update
                    print(f"Room creation note (likely exists): {create_err}. Updating metadata...")
                    await lkapi.room.update_room_metadata(api.UpdateRoomMetadataRequest(
                        room=request.room_name,
                        metadata=meta_json
                    ))
                    print(f"Updated metadata for room '{request.room_name}'.")
                    
            except Exception as e:
                print(f"ERROR: Failed to set room metadata: {e}")
            finally:
                await lkapi.aclose()

        # Generate unique identity
        participant_identity = f"{request.participant_name}_{os.urandom(4).hex()}"
        
        # Create access token
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(participant_identity)
        token.with_name(request.participant_name)
        token.with_ttl(timedelta(hours=2))
        
        # Grant permissions
        token.with_grants(api.VideoGrants(
            room_join=True,
            room=request.room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
        
        jwt_token = token.to_jwt()
        
        return TokenResponse(
            token=jwt_token,
            url=LIVEKIT_URL,
            room_name=request.room_name
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create token: {str(e)}")





@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    """Demo page for AI Voice Agent"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Voice Agent Demo</title>
        <script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Lato:wght@300;400&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-color: #0d0d12;
                --card-bg: rgba(20, 20, 25, 0.95);
                --text-primary: #e0e0e0;
                --text-secondary: #a0a0a0;
                --gold-accent: #d4af37;
                --gold-dim: #8a7224;
                --blood-red: #8a1c1c;
                --mystery-purple: #2d1b4e;
                --shadow: 0 10px 30px rgba(0,0,0,0.8);
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Lato', sans-serif;
                background-color: var(--bg-color);
                background-image: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.4)), url('/bg.gif');
                background-size: cover;
                background-position: top center;
                background-repeat: no-repeat;
                background-attachment: fixed;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                color: var(--text-primary);
            }

            .container {
                background: var(--card-bg);
                border: 1px solid var(--gold-dim);
                border-radius: 4px;
                box-shadow: 0 0 20px rgba(0,0,0,0.9), 0 0 10px rgba(212, 175, 55, 0.1);
                padding: 40px;
                max-width: 650px;
                width: 100%;
                position: relative;
            }
            
            /* Decorative Corners */
            .container::before, .container::after {
                content: '';
                position: absolute;
                width: 20px;
                height: 20px;
                border: 2px solid var(--gold-accent);
                transition: all 0.3s ease;
            }
            .container::before { top: 10px; left: 10px; border-right: none; border-bottom: none; }
            .container::after { bottom: 10px; right: 10px; border-left: none; border-top: none; }

            h1 {
                font-family: 'Cinzel', serif;
                color: var(--gold-accent);
                text-align: center;
                margin-bottom: 5px;
                font-size: 2.5em;
                text-transform: uppercase;
                letter-spacing: 2px;
                text-shadow: 2px 2px 4px #000;
            }

            .subtitle {
                font-family: 'Playfair Display', serif;
                text-align: center;
                color: var(--text-secondary);
                margin-bottom: 35px;
                font-size: 1.1em;
                font-style: italic;
                letter-spacing: 1px;
            }

            .tech-stack {
                display: flex;
                justify-content: center;
                gap: 12px;
                margin-bottom: 30px;
                flex-wrap: wrap;
                opacity: 0.8;
            }

            .tech-badge {
                background: rgba(0,0,0,0.4);
                color: var(--text-secondary);
                border: 1px solid #333;
                padding: 4px 10px;
                border-radius: 2px;
                font-size: 0.75em;
                font-family: monospace;
                text-transform: uppercase;
            }

            .form-group {
                margin-bottom: 25px;
            }

            label {
                display: block;
                margin-bottom: 10px;
                font-family: 'Cinzel', serif;
                color: var(--gold-accent);
                font-size: 0.9em;
                letter-spacing: 1px;
            }

            input, select {
                width: 100%;
                padding: 15px;
                background: rgba(0,0,0,0.6);
                border: 1px solid #444;
                border-left: 3px solid var(--gold-dim);
                color: #fff;
                font-family: 'Lato', sans-serif;
                font-size: 16px;
                transition: all 0.3s;
            }

            input:focus, select:focus {
                outline: none;
                border-color: var(--gold-accent);
                background: rgba(20,20,20,0.8);
                box-shadow: 0 0 10px rgba(212, 175, 55, 0.2);
            }

            .status {
                padding: 15px;
                margin-bottom: 25px;
                font-family: 'Playfair Display', serif;
                text-align: center;
                letter-spacing: 1px;
                border: 1px solid transparent;
                background: rgba(0,0,0,0.3);
            }

            .status.info { color: var(--text-secondary); border-color: #444; }
            .status.success { color: #4caf50; border-color: #1b5e20; background: rgba(27, 94, 32, 0.1); text-shadow: 0 0 5px #4caf50; }
            .status.error { color: #e57373; border-color: var(--blood-red); background: rgba(183, 28, 28, 0.1); }
            .status.warning { color: #ffb74d; border-color: #e65100; }

            button {
                width: 100%;
                padding: 18px;
                border: 1px solid var(--gold-dim);
                background: linear-gradient(to bottom, #1a1a1a, #000);
                color: var(--gold-accent);
                font-family: 'Cinzel', serif;
                font-size: 1.1em;
                text-transform: uppercase;
                letter-spacing: 2px;
                cursor: pointer;
                transition: all 0.3s;
                margin-bottom: 15px;
                position: relative;
                overflow: hidden;
            }

            button::before {
                content: '';
                position: absolute;
                top: 0; left: -100%;
                width: 100%; height: 100%;
                background: linear-gradient(90deg, transparent, rgba(212, 175, 55, 0.2), transparent);
                transition: 0.5s;
            }

            button:hover:not(:disabled)::before {
                left: 100%;
            }

            button:hover:not(:disabled) {
                border-color: var(--gold-accent);
                box-shadow: 0 0 15px rgba(212, 175, 55, 0.3);
                text-shadow: 0 0 5px var(--gold-accent);
            }

            .btn-danger {
                border-color: var(--blood-red);
                color: #ff5252;
            }

            .btn-danger:hover:not(:disabled) {
                border-color: #ff1744;
                box-shadow: 0 0 15px rgba(255, 23, 68, 0.3);
                text-shadow: 0 0 5px #ff1744;
            }

            button:disabled {
                opacity: 0.3;
                cursor: not-allowed;
                border-color: #333;
                color: #555;
            }

            .participants {
                background: rgba(0,0,0,0.5);
                border: 1px solid #333;
                padding: 15px;
                margin-top: 25px;
            }

            .participants h3 {
                color: var(--text-secondary);
                font-family: 'Cinzel', serif;
                font-size: 0.9em;
                border-bottom: 1px solid #333;
                padding-bottom: 5px;
                margin-bottom: 10px;
            }

            .participant {
                padding: 8px;
                border-bottom: 1px solid #222;
                color: #bbb;
                font-size: 0.9em;
            }

            .participant.agent {
                color: var(--gold-accent);
                text-shadow: 0 0 2px var(--gold-dim);
            }

            .audio-visualizer {
                height: 60px;
                background: rgba(0,0,0,0.3);
                border: 1px solid #333;
                margin-top: 25px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 5px;
                padding: 0 20px;
            }

            .bar {
                width: 3px;
                background: #444;
                box-shadow: 0 0 2px #000;
                transition: height 0.05s ease;
            }

            .speaking {
                background: var(--gold-accent) !important;
                box-shadow: 0 0 8px var(--gold-accent);
            }

            .kb-section {
                background: rgba(10, 10, 15, 0.6);
                border: 1px solid var(--mystery-purple);
                padding: 20px;
                margin-bottom: 30px;
                position: relative;
            }
            .kb-section::before {
                content: 'CASE FILES';
                position: absolute;
                top: -10px;
                left: 20px;
                background: var(--card-bg);
                padding: 0 10px;
                font-family: 'Cinzel', serif;
                font-size: 0.8em;
                color: var(--mystery-purple);
            }

            .section-divider {
                border-top: 1px solid #333;
                text-align: center;
                padding-top: 20px;
                margin-top: 20px;
            }
            .section-divider h2 {
                color: var(--text-secondary);
                font-family: 'Cinzel', serif;
                font-size: 1.2em;
                display: inline-block;
                background: var(--card-bg);
                position: relative;
                top: -32px;
                padding: 0 15px;
            }

            .debug {
                background: #000;
                border: 1px solid #333;
                color: #0f0;
                margin-top: 15px;
                font-family: 'Courier New', monospace;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🕵️‍♂️ Moriarty's Game</h1>
            <p class="subtitle">"The game is afoot, my dear detective..."</p>
            
            <div class="tech-stack">
                <span class="tech-badge">🎤 Deepgram</span>
                <span class="tech-badge">🧠 openai LLM</span>
                <span class="tech-badge">🔊 Cartesia</span>
                <span class="tech-badge">📞 LiveKit</span>
            </div>

            <!-- Voice Chat Section -->
            <div class="section-divider">
                <h2>🎙️ Voice Chat</h2>
            </div>

            <div id="status" class="status info">
                Ready to connect
            </div>

            <div class="form-group">
                <label for="roomName">Room Name</label>
                <input type="text" id="roomName" placeholder="Enter room name" value="voice-room">
            </div>

            <div class="form-group">
                <label for="userName">Your Name</label>
                <input type="text" id="userName" placeholder="Enter your name" value="User">
            </div>

            <!-- Crime Scene Injection -->
            <div class="kb-section">
                <h2 style="color: var(--gold-accent);">🕵️‍♀️ Crime Scene Settings</h2>
                
                <!-- Scenario Preset -->
                <div class="form-group">
                    <label>Scenario Preset</label>
                    <select id="scenarioPreset" onchange="applyPreset()" style="background: rgba(0,0,0,0.6); border: 1px solid #444; color: #fff;">
                        <option value="custom">Custom</option>
                        <option value="indian_kidnap">Moriarty's Kidnapping (Indian Edition)</option>
                        <option value="indian_bomb">Moriarty's Bombing Plot (Indian Edition)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Crime Type</label>
                    <input type="text" id="crimeType" placeholder="e.g. Bank Heist, Murder Mystery" style="color: #fff;">
                </div>
                <div class="form-group">
                    <label>Victim Name (if applicable)</label>
                    <input type="text" id="victimName" placeholder="e.g. Priya, Rahul" value="" style="color: #fff;">
                </div>
                <div class="form-group">
                    <label>Complexity</label>
                    <select id="crimeComplexity" style="background: rgba(0,0,0,0.6); border: 1px solid #444; color: #fff;">
                        <option value="">Normal</option>
                        <option value="Low">Low</option>
                        <option value="High">High</option>
                        <option value="Impossible">Impossible</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Your Role</label>
                    <input type="text" id="userRole" placeholder="e.g. Detective, Suspect" value="Detective" style="color: #fff;">
                </div>
                <!-- Volume Control -->
                <div class="form-group">
                    <label>Background Music Volume (0 - 1)</label>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input type="range" id="bgVolume" min="0" max="1" step="0.1" value="0.2" oninput="document.getElementById('volValue').innerText = this.value">
                        <span id="volValue" style="color: var(--gold-accent)">0.2</span>
                    </div>
                </div>

                <script>
                function applyPreset() {
                    const preset = document.getElementById('scenarioPreset').value;
                    if (preset === 'indian_kidnap') {
                        document.getElementById('crimeType').value = 'Kidnapping (Indian Edition)';
                        document.getElementById('victimName').value = 'Priya';
                        document.getElementById('crimeComplexity').value = 'High';
                        document.getElementById('userRole').value = 'Detective';
                    } else if (preset === 'indian_bomb') {
                        document.getElementById('crimeType').value = 'Bombing (Indian Edition)';
                        document.getElementById('victimName').value = 'N/A';
                        document.getElementById('crimeComplexity').value = 'Impossible';
                        document.getElementById('userRole').value = 'Bomb Specialist';
                    } else {
                        document.getElementById('crimeType').value = '';
                        document.getElementById('victimName').value = '';
                        document.getElementById('crimeComplexity').value = '';
                    }
                }
                </script>
            </div>

            <button class="btn-primary" onclick="joinCall()" id="joinBtn">
                🎙️ Start Voice Call
            </button>

            <button class="btn-danger" onclick="leaveCall()" id="leaveBtn" disabled>
                📞 End Call
            </button>

            <div class="audio-visualizer" id="visualizer" style="display: none;">
                <div class="bar" style="height: 20px;"></div>
                <div class="bar" style="height: 35px;"></div>
                <div class="bar" style="height: 25px;"></div>
                <div class="bar" style="height: 40px;"></div>
                <div class="bar" style="height: 30px;"></div>
                <div class="bar" style="height: 45px;"></div>
                <div class="bar" style="height: 25px;"></div>
                <div class="bar" style="height: 35px;"></div>
                <div class="bar" style="height: 20px;"></div>
            </div>

            <div class="participants" id="participants" style="display: none;">
                <h3>📋 Participants</h3>
                <div id="participantList"></div>
            </div>

            <div class="debug" id="debug" style="display: none;">
                <strong>Debug Log:</strong>
                <div id="debugLog"></div>
            </div>
        </div>

        <script>
            let room;
            let isConnected = false;
            let audioContext;
            let analyser;
            let dataArray;
            const API_URL = window.location.origin;

            async function extractKnowledgeBase() {
                const websiteUrl = document.getElementById('websiteUrl').value.trim();
                const maxPages = parseInt(document.getElementById('maxPages').value) || 50;
                const statusDiv = document.getElementById('extractionStatus');
                const extractBtn = document.getElementById('extractBtn');

                if (!websiteUrl) {
                    statusDiv.style.display = 'block';
                    statusDiv.className = 'status error';
                    statusDiv.textContent = 'Please enter a website URL';
                    return;
                }

                try {
                    new URL(websiteUrl);
                } catch (e) {
                    statusDiv.style.display = 'block';
                    statusDiv.className = 'status error';
                    statusDiv.textContent = 'Please enter a valid URL (e.g., https://example.com)';
                    return;
                }

                try {
                    extractBtn.disabled = true;
                    statusDiv.style.display = 'block';
                    statusDiv.className = 'status info';
                    statusDiv.textContent = `⏳ Extracting knowledge base from ${websiteUrl}... This may take a few minutes.`;

                    const response = await fetch(`${API_URL}/extract-knowledge-base`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            website_url: websiteUrl,
                            max_pages: maxPages
                        })
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to extract knowledge base');
                    }

                    const data = await response.json();
                    statusDiv.className = 'status success';
                    statusDiv.innerHTML = `✅ ${data.message}<br><small>Output saved to: ${data.output_dir}</small>`;

                } catch (error) {
                    console.error('Extraction error:', error);
                    statusDiv.className = 'status error';
                    statusDiv.textContent = `❌ Failed: ${error.message}`;
                } finally {
                    extractBtn.disabled = false;
                }
            }

            function setStatus(message, type = 'info') {
                const status = document.getElementById('status');
                status.textContent = message;
                status.className = `status ${type}`;
            }

            function addDebug(message) {
                const debugLog = document.getElementById('debugLog');
                const entry = document.createElement('div');
                entry.className = 'debug-entry';
                entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
                debugLog.appendChild(entry);
                debugLog.scrollTop = debugLog.scrollHeight;
                console.log(message);
            }

            function updateParticipants() {
                if (!room) return;
                
                const participantList = document.getElementById('participantList');
                participantList.innerHTML = '';
                
                const localDiv = document.createElement('div');
                localDiv.className = 'participant';
                localDiv.innerHTML = `👤 ${room.localParticipant.name || room.localParticipant.identity} (You)`;
                participantList.appendChild(localDiv);
                
                room.remoteParticipants.forEach(participant => {
                    const div = document.createElement('div');
                    const isAgent = participant.identity.toLowerCase().includes('agent') || 
                                   participant.name?.toLowerCase().includes('agent');
                    div.className = `participant ${isAgent ? 'agent' : ''}`;
                    div.innerHTML = `${isAgent ? '🤖' : '👤'} ${participant.name || participant.identity}`;
                    participantList.appendChild(div);
                });
                
                document.getElementById('participants').style.display = 'block';
            }

            function setupAudioVisualization(track) {
                try {
                    if (!audioContext) {
                        audioContext = new (window.AudioContext || window.webkitAudioContext)();
                        analyser = audioContext.createAnalyser();
                        analyser.fftSize = 32;
                        dataArray = new Uint8Array(analyser.frequencyBinCount);
                    }
                    
                    const stream = new MediaStream([track.mediaStreamTrack]);
                    const source = audioContext.createMediaStreamSource(stream);
                    source.connect(analyser);
                    
                    animateBars();
                } catch (e) {
                    addDebug('Audio visualization error: ' + e.message);
                }
            }

            function animateBars() {
                if (!isConnected || !analyser) return;
                
                analyser.getByteFrequencyData(dataArray);
                const bars = document.querySelectorAll('.bar');
                
                bars.forEach((bar, i) => {
                    const value = dataArray[i] || 0;
                    const height = (value / 255) * 40 + 10;
                    bar.style.height = height + 'px';
                    bar.classList.toggle('speaking', value > 30);
                });
                
                requestAnimationFrame(animateBars);
            }

            async function joinCall() {
                const roomName = document.getElementById('roomName').value.trim();
                const userName = document.getElementById('userName').value.trim();

                if (!roomName || !userName) {
                    setStatus('Please enter both room name and your name', 'error');
                    return;
                }

                try {
                    setStatus('Connecting to room...', 'info');
                    document.getElementById('debug').style.display = 'block';
                    addDebug('Starting connection process...');

                    addDebug(`Requesting token for room: ${roomName}`);
                    const response = await fetch(`${API_URL}/token`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            room_name: roomName,
                            participant_name: userName,
                            metadata: {
                                crime_type: document.getElementById('crimeType').value,
                                victim_name: document.getElementById('victimName').value,
                                complexity: document.getElementById('crimeComplexity').value,
                                user_role: document.getElementById('userRole').value,
                                bg_volume: document.getElementById('bgVolume').value
                            }
                        })
                    });

                    if (!response.ok) {
                        throw new Error(`Failed to get access token: ${response.statusText}`);
                    }

                    const data = await response.json();
                    addDebug('Token received successfully');

                    room = new LivekitClient.Room({
                        adaptiveStream: true,
                        dynacast: true,
                        audioCaptureDefaults: {
                            autoGainControl: true,
                            echoCancellation: true,
                            noiseSuppression: true,
                        },
                    });

                    room.on('connected', () => {
                        addDebug('Connected to room successfully');
                        setStatus('✅ Connected! Waiting for AI agent...', 'success');
                        isConnected = true;
                        document.getElementById('visualizer').style.display = 'flex';
                        updateParticipants();
                        updateButtons(true);
                    });

                    room.on('disconnected', (reason) => {
                        addDebug('Disconnected from room: ' + reason);
                        setStatus('Disconnected', 'info');
                        isConnected = false;
                        updateButtons(false);
                        document.getElementById('visualizer').style.display = 'none';
                        document.getElementById('participants').style.display = 'none';
                    });

                    room.on('participantConnected', (participant) => {
                        addDebug(`Participant connected: ${participant.identity}`);
                        const isAgent = participant.identity.toLowerCase().includes('agent') || 
                                       participant.name?.toLowerCase().includes('agent');
                        
                        if (isAgent) {
                            setStatus('🤖 AI Agent is ready! Start speaking...', 'success');
                        }
                        updateParticipants();
                    });

                    room.on('participantDisconnected', (participant) => {
                        addDebug(`Participant disconnected: ${participant.identity}`);
                        updateParticipants();
                    });

                    room.on('trackSubscribed', (track, publication, participant) => {
                        addDebug(`Track subscribed: ${track.kind} from ${participant.identity}`);
                        
                        if (track.kind === 'audio') {
                            const isAgent = participant.identity.toLowerCase().includes('agent') || 
                                           participant.name?.toLowerCase().includes('agent');
                            
                            if (isAgent) {
                                addDebug('Playing agent audio');
                                const audioElement = track.attach();
                                audioElement.volume = 1.0;
                                document.body.appendChild(audioElement);
                            }
                        }
                    });

                    room.on('trackUnsubscribed', (track, publication, participant) => {
                        addDebug(`Track unsubscribed: ${track.kind} from ${participant.identity}`);
                        track.detach();
                    });

                    room.on('audioPlaybackStatusChanged', () => {
                        if (!room.canPlaybackAudio) {
                            addDebug('Audio playback blocked - user interaction required');
                            setStatus('⚠️ Click anywhere to enable audio', 'warning');
                            
                            const enableAudio = async () => {
                                await room.startAudio();
                                addDebug('Audio playback enabled');
                                setStatus('🤖 AI Agent is ready! Start speaking...', 'success');
                                document.removeEventListener('click', enableAudio);
                            };
                            
                            document.addEventListener('click', enableAudio, { once: true });
                        }
                    });

                    addDebug(`Connecting to ${data.url}...`);
                    await room.connect(data.url, data.token);

                    addDebug('Enabling microphone...');
                    await room.localParticipant.setMicrophoneEnabled(true);
                    addDebug('Microphone enabled');

                    const localAudioTrack = room.localParticipant.audioTrackPublications.values().next().value?.track;
                    if (localAudioTrack) {
                        setupAudioVisualization(localAudioTrack);
                    }

                    const agentPresent = Array.from(room.remoteParticipants.values()).some(p => 
                        p.identity.toLowerCase().includes('agent') || p.name?.toLowerCase().includes('agent')
                    );

                    if (!agentPresent) {
                        setStatus('⏳ Waiting for AI agent to join...', 'warning');
                        addDebug('No agent detected in room yet');
                    }

                } catch (error) {
                    console.error('Error joining call:', error);
                    addDebug('ERROR: ' + error.message);
                    setStatus('❌ Failed to join: ' + error.message, 'error');
                    updateButtons(false);
                }
            }

            async function leaveCall() {
                if (room) {
                    addDebug('Leaving call...');
                    await room.disconnect();
                    room = null;
                    isConnected = false;
                    
                    if (audioContext) {
                        audioContext.close();
                        audioContext = null;
                        analyser = null;
                    }
                    
                    setStatus('Call ended', 'info');
                    updateButtons(false);
                    document.getElementById('visualizer').style.display = 'none';
                    document.getElementById('participants').style.display = 'none';
                }
            }

            function updateButtons(connected) {
                document.getElementById('joinBtn').disabled = connected;
                document.getElementById('leaveBtn').disabled = !connected;
                document.getElementById('roomName').disabled = connected;
                document.getElementById('userName').disabled = connected;
            }

            window.addEventListener('beforeunload', () => {
                if (room) room.disconnect();
            });
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)