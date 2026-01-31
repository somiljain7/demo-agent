from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
                # Try to create room with metadata (handles if it doesn't exist)
                # If it exists, we might need to update it.
                # Simplest check: List rooms to see if it exists
                rooms = await lkapi.room.list_rooms(api.ListRoomsRequest(names=[request.room_name]))
                
                if rooms.rooms:
                    # Update existing room
                    await lkapi.room.update_room_metadata(api.UpdateRoomMetadataRequest(
                        room=request.room_name,
                        metadata=meta_json
                    ))
                else:
                    # Create new room with metadata
                    await lkapi.room.create_room(api.CreateRoomRequest(
                        name=request.room_name,
                        metadata=meta_json
                    ))
            except Exception as e:
                print(f"Warning: Failed to update room metadata: {e}")
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
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
                max-width: 600px;
                width: 100%;
            }
            h1 {
                color: #667eea;
                text-align: center;
                margin-bottom: 10px;
                font-size: 2em;
            }
            .subtitle {
                text-align: center;
                color: #666;
                margin-bottom: 30px;
                font-size: 0.9em;
            }
            .tech-stack {
                display: flex;
                justify-content: center;
                gap: 15px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }
            .tech-badge {
                background: #f0f4ff;
                color: #667eea;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 600;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #333;
            }
            input {
                width: 100%;
                padding: 14px;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                font-size: 16px;
                transition: border-color 0.3s;
            }
            input:focus {
                outline: none;
                border-color: #667eea;
            }
            .status {
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
                font-weight: 500;
                text-align: center;
            }
            .status.info {
                background: #dbeafe;
                color: #1e40af;
            }
            .status.success {
                background: #d1fae5;
                color: #065f46;
            }
            .status.error {
                background: #fee2e2;
                color: #991b1b;
            }
            .status.warning {
                background: #fef3c7;
                color: #92400e;
            }
            button {
                width: 100%;
                padding: 16px;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                margin-bottom: 10px;
            }
            .btn-primary {
                background: #667eea;
                color: white;
            }
            .btn-primary:hover:not(:disabled) {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            .btn-danger {
                background: #ef4444;
                color: white;
            }
            .btn-danger:hover:not(:disabled) {
                background: #dc2626;
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(239, 68, 68, 0.3);
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none !important;
            }
            .participants {
                background: #f9fafb;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                padding: 15px;
                margin-top: 20px;
                font-size: 14px;
            }
            .participants h3 {
                margin-bottom: 10px;
                color: #374151;
                font-size: 14px;
            }
            .participant {
                padding: 8px;
                background: white;
                border-radius: 6px;
                margin-bottom: 6px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .participant.agent {
                background: #dcfce7;
            }
            .audio-visualizer {
                height: 60px;
                background: #f0f4ff;
                border-radius: 10px;
                margin-top: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 4px;
                padding: 0 20px;
            }
            .bar {
                width: 4px;
                background: #667eea;
                border-radius: 2px;
                transition: height 0.1s;
            }
            .speaking {
                background: #10b981 !important;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .recording {
                animation: pulse 1.5s infinite;
            }
            .debug {
                background: #f3f4f6;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 10px;
                margin-top: 15px;
                font-size: 12px;
                font-family: monospace;
                max-height: 200px;
                overflow-y: auto;
            }
            .debug-entry {
                padding: 4px 0;
                border-bottom: 1px solid #e5e7eb;
            }
            .kb-section {
                background: #f0f9ff;
                border: 2px solid #0ea5e9;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 30px;
            }
            .kb-section h2 {
                color: #0369a1;
                margin-bottom: 10px;
                font-size: 1.3em;
            }
            .kb-section p {
                color: #666;
                margin-bottom: 20px;
                font-size: 0.9em;
            }
            .section-divider {
                border-top: 2px solid #e5e7eb;
                padding-top: 30px;
            }
            .section-divider h2 {
                color: #667eea;
                margin-bottom: 20px;
                font-size: 1.3em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 AI Voice Agent</h1>
            <p class="subtitle">Talk naturally with an AI assistant</p>
            
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
            <div class="kb-section" style="margin-top: 20px; border-color: #7c3aed; background: #faf5ff;">
                <h2 style="color: #6d28d9;">🕵️‍♀️ Crime Scene Settings</h2>
                <div class="form-group">
                    <label>Crime Type</label>
                    <input type="text" id="crimeType" placeholder="e.g. Bank Heist, Murder Mystery">
                </div>
                <div class="form-group">
                    <label>Complexity</label>
                    <select id="crimeComplexity" style="width: 100%; padding: 14px; border: 2px solid #e0e0e0; border-radius: 10px;">
                        <option value="">Normal</option>
                        <option value="Low">Low</option>
                        <option value="High">High</option>
                        <option value="Impossible">Impossible</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Your Role</label>
                    <input type="text" id="userRole" placeholder="e.g. Detective, Suspect" value="Detective">
                </div>
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
                                complexity: document.getElementById('crimeComplexity').value,
                                user_role: document.getElementById('userRole').value
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