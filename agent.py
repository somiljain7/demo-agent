import logging
import os
import sys
import asyncio
from typing import Optional
from dotenv import load_dotenv
from persona import get_criminal_mindset_prompt
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    APIConnectOptions,
    cli,
    metrics,
)
from livekit.plugins import  noise_cancellation, silero
from livekit.plugins import deepgram, groq, cartesia, silero, openai
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import ChatContext, ChatMessage, llm
import aiohttp
from livekit import rtc

logger = logging.getLogger("agent-worker")
logging.basicConfig(level=logging.INFO)

load_dotenv(".env")



class VoiceAssistant(Agent):
    """Voice AI Assistant Agent"""
    
    def __init__(self, instructions: Optional[str] = None) -> None:
        default_instructions = """You are an intelligent voice assistant embedded on a website, helping visitors get the information they need quickly and efficiently.

CORE IDENTITY:
- You represent this website and speak on its behalf
- You have access to relevant knowledge about the website's content, products, services, and policies
- You communicate naturally through voice, so keep responses conversational and concise

COMMUNICATION STYLE:
- Speak in a natural, conversational tone as if having a face-to-face conversation
- Keep responses brief and scannable - aim for 2-3 sentences unless more detail is requested
- Avoid bullet points, markdown formatting, and complex punctuation
- Never use emojis, asterisks, or special characters
- If you need to list items, speak them naturally: "There are three options: first, second, and third"

CAPABILITIES:
- Answer questions about website content, features, and offerings
- Guide users to relevant pages or sections
- Provide summaries of complex information in simple terms
- Help with navigation and next steps
- Clarify policies, pricing, and processes

HANDLING QUERIES:
- When you receive additional context from the knowledge base, integrate it naturally without mentioning "according to documents" or "based on provided information"
- If you don't know something, be honest and offer to help find the information or direct them to contact support
- For complex requests, break down your response into digestible parts
- Always confirm understanding before providing detailed answers to ambiguous questions

BOUNDARIES:
- Stay focused on website-related information and assistance
- For questions outside your knowledge base, politely redirect to appropriate resources
- Never make up information - if unsure, say so
- Don't make promises about features, pricing, or policies unless explicitly stated in your knowledge base

TONE: Professional yet friendly, helpful, and efficient. You're here to make their experience easier."""

        
        super().__init__(
            instructions=instructions or default_instructions,
        )
    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage,
    ) -> None:
        pass


# Global VAD instance for efficiency
vad_instance = None


class WatsonActions:
    def __init__(self, room: rtc.Room):
        self.room = room
        self.watson_voice_id = "0ad65e7f-006c-47cf-bd31-52279d487913" # Official Watson Voice

    @llm.function_tool(description="Consult Dr. Watson for his medical or military opinion, or just for support.")
    async def ask_watson(self, query: str):
        """
        Consult Dr. Watson.

        Args:
            query: The question or statement to address to Dr. Watson
        """
        logger.info(f"🎤 Asking Watson: {query}")
        
        # 1. Generate Watson's text response using a separate LLM call
        # We use a transient LLM instance for this to keep it simple
        # watson_llm = openai.LLM(model="o3-mini")
        watson_llm = groq.LLM(
            model="openai/gpt-oss-20b",
            api_key=os.getenv("GROQ_API_KEY"),
        )
        
        system_prompt = """You are Dr. John Watson, Sherlock Holmes's loyal partner.
        - You are British, practical, and grounded.
        - You represent the user's ally against Moriarty.
        - Speak with a British accent.
        - Keep responses short (1-2 sentences).
        - Do not solve the riddles, but offer medical/military insights.
        - SUPPORT THE USER.
        """
        
        chat_ctx = llm.ChatContext()
        chat_ctx.add_message(role="system", content=system_prompt)
        chat_ctx.add_message(role="user", content=query)
        
        try:
            stream = watson_llm.chat(
                chat_ctx=chat_ctx,
                conn_options=APIConnectOptions(timeout=60.0)
            )
            watson_response_text = ""
            async for chunk in stream:
                if chunk.delta and chunk.delta.content:
                    watson_response_text += chunk.delta.content
        except Exception as e:
            logger.error(f"Watson LLM failed: {e}")
            watson_response_text = "I cannot form a thought right now. The fog is too thick."
        
        logger.info(f"Watson says: {watson_response_text}")

        # 2. Synthesize Audio using Cartesia (Sonic-2)
        # We need to manually handle the audio source publication
        try:
             # Create source and track for Watson
            source = rtc.AudioSource(24000, 1)
            track = rtc.LocalAudioTrack.create_audio_track("watson_audio", source)
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            publication = await self.room.local_participant.publish_track(track, options)
            
            # Initialize Cartesia manually
            # specific model and voice as requested/fixed
            async with aiohttp.ClientSession() as http_session:
                tts = cartesia.TTS(model="sonic-2", voice=self.watson_voice_id, http_session=http_session)

                stream = tts.synthesize(text=watson_response_text)
                
                async for chunk in stream:
                    # chunk is SynthesizedAudio
                    # It has .frame which is rtc.AudioFrame
                    if chunk.frame:
                        await source.capture_frame(chunk.frame)
                        
            # Simple heuristic to prevent Moriarty from speaking over Watson
            # Approx 15 chars per second
            estimated_duration = len(watson_response_text) / 15.0
            logger.info(f"Generated {len(watson_response_text)} chars. Waiting {estimated_duration:.2f}s for playback...")
            await asyncio.sleep(estimated_duration)

            # Clean up
            await self.room.local_participant.unpublish_track(publication.sid)

        except Exception as e:
            logger.error(f"Watson TTS failed: {e}", exc_info=True)

        return f"Watson replied: '{watson_response_text}'"



def get_vad():
    """Get or initialize VAD instance"""
    global vad_instance
    if vad_instance is None:
        logger.info("Loading VAD model...")
        vad_instance = silero.VAD.load()
    return vad_instance


async def entrypoint(ctx: JobContext):
    """
    Main entrypoint for the agent worker.
    This is called when a room is created or when an agent is requested.
    """
    logger.info(f"Starting agent for room: {ctx.room.name}")
    
    # Explicitly fetch fresh room metadata to avoid race conditions
    room_metadata = ctx.room.metadata
    
    try:
        from livekit import api
        lkapi = api.LiveKitAPI(os.getenv("LIVEKIT_URL"), os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
        rooms = await lkapi.room.list_rooms(api.ListRoomsRequest(names=[ctx.room.name]))
        if rooms.rooms:
            room_metadata = rooms.rooms[0].metadata
            logger.info(f"🔄 FRESH METADATA FETCHED: {room_metadata}")
        await lkapi.aclose()
    except Exception as e:
        logger.warning(f"Failed to fetch fresh metadata, using context metadata: {e}")

    if not room_metadata:
        logger.warning("⚠️ NO ROOM METADATA FOUND. Persona will default to standard assistant.")
    else:
        logger.info(f"✅ METADATA RECEIVED: {room_metadata}")
    
    room_metadata = room_metadata or "{}"
    
    # Parse metadata for custom instructions
    # Parse metadata for custom instructions
    instructions = None
    
    # Default Configuration with Real Plugins
    stt = deepgram.STT(language="hi", model="nova-3")
    llm = groq.LLM(model="llama-3.3-70b-versatile")
    # Using 'Hindi Narrator Man' for Moriarty to ensure Hindi compatibility
    tts = cartesia.TTS(model="sonic-2", voice="7f423809-0011-4658-ba48-a411f5e516ba")
    
    try:
        import json
        metadata = json.loads(room_metadata)
        instructions = metadata.get("instructions")
        
        # Allow metadata to override models if provided
        # Note: This simple overrides assumes the same provider. 
        # For more complex switching, we'd need a factory pattern.
        if metadata.get("llm_model"):
             # Attempt to use the provided model string with Groq if compatible, or just log
             # For this task, we assume we stick to Groq/Cartesia/Deepgram but allow model tuning
             llm = groq.LLM(model=metadata.get("llm_model"))
    except Exception as e:
        logger.warning(f"Could not parse room metadata: {e}")

    # Check for Riddler/Moriarty persona trigger
    if instructions is None and "crime_type" in metadata or "riddler" in str(metadata).lower():
        logger.info("Activating Riddler/Moriarty Persona")
        instructions = get_criminal_mindset_prompt(metadata)

    
    # Initialize usage collector for metrics
    usage_collector = metrics.UsageCollector()
    

    
    if instructions:
        watson = WatsonActions(room=ctx.room)
        session = AgentSession(
            stt=stt,
            llm=llm,
            tts=tts,
            tools=[watson.ask_watson],
            turn_detection=MultilingualModel(),
            preemptive_generation=True,
        )
    else:
         session = AgentSession(
            stt=stt,
            llm=llm,
            tts=tts,
            turn_detector=MultilingualModel(),
            preemptive_generation=True,
        )

    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        """Log metrics when collected"""
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        """Log usage summary on shutdown"""
        summary = usage_collector.get_summary()
        logger.info(f"Session usage summary: {summary}")
    
    # Register shutdown callback
    ctx.add_shutdown_callback(log_usage)
    
    # Start the agent session
    await session.start(
        agent=VoiceAssistant(instructions=instructions),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),  # Background voice cancellation
        ),
    )
    
    # Connect to the room
    await ctx.connect()
    
    # --------------------------------------------------------------------------
    # Audio Playback Logic
    # --------------------------------------------------------------------------
    from livekit import rtc
    import asyncio
    
    async def _play_audio_file(file_path: str, loop: bool = False, volume: float = 1.0):
        """Plays an audio file into the room."""
        try:
            source = rtc.AudioSource(24000, 1) # 24kHz, 1 channel
            track = rtc.LocalAudioTrack.create_audio_track("audio_player", source)
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            publication = await ctx.room.local_participant.publish_track(track, options)
            
            import av

            while True:
                try:
                    container = av.open(file_path)
                    stream = container.streams.audio[0]
                    resampler = av.AudioResampler(
                        format='s16',
                        layout='mono',
                        rate=24000,
                    )

                    for frame in container.decode(stream):
                        frames = resampler.resample(frame)
                        for f in frames:
                           data = f.to_ndarray().tobytes()
                           if volume != 1.0:
                               import numpy as np
                               audio_data = np.frombuffer(data, dtype=np.int16)
                               audio_data = (audio_data * volume).astype(np.int16)
                               data = audio_data.tobytes()
                               
                           audio_frame = rtc.AudioFrame(
                               data=data,
                               sample_rate=24000,
                               num_channels=1,
                               samples_per_channel=f.samples
                           )
                           await source.capture_frame(audio_frame)
                    
                    container.close()
                    
                except Exception as e:
                    logger.error(f"Error reading audio file {file_path}: {e}")
                    break
                    
                if not loop:
                    break
                    
            await ctx.room.local_participant.unpublish_track(publication.sid)
            
        except Exception as e:
             logger.error(f"Failed to play audio {file_path}: {e}")

    # 1. Play Intro Sound (Machine Gun)
    intro_path = os.path.join(os.path.dirname(__file__), "playback_audios", "machine-gun-01.wav")
    if os.path.exists(intro_path):
        logger.info(f"Playing intro audio: {intro_path}")
        # Run in background (fire and forget? or wait?) - Wait so it plays BEFORE hello
        await _play_audio_file(intro_path, loop=False, volume=0.5)
    else:
        logger.warning(f"Intro audio not found at: {intro_path}")

    # 2. Start Background Loop (Fire and forget task)
    bg_path = os.path.join(os.path.dirname(__file__), "playback_audios", "bg.mp3")
    if os.path.exists(bg_path):
        bg_volume = 0.1
        try:
             if "bg_volume" in metadata:
                 bg_volume = float(metadata.get("bg_volume"))
        except: pass
        
        logger.info(f"Starting background audio: {bg_path} (Vol: {bg_volume})")
        asyncio.create_task(_play_audio_file(bg_path, loop=True, volume=bg_volume))
    else:
        logger.warning(f"Background audio not found at: {bg_path}")
    
    # --------------------------------------------------------------------------
    
    # --------------------------------------------------------------------------
    
    # 3. Dynamic Greeting based on Persona
    # --------------------------------------------------------------------------
    
    # 3. Dynamic Greeting based on Persona
    initial_greeting = "Hello. How can I help you today?"
    if instructions:
         initial_greeting = "Welcome Sherlock and Watson to the game of LIFE!"
         
    # Audio playback logic and greeting are handled below
    
    await session.say(
       initial_greeting,
       allow_interruptions=False,
    )
    logger.info(f"Agent successfully started in room: {ctx.room.name}")



if __name__ == "__main__":
    # Run the agent worker
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )