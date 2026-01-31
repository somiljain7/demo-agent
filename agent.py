import logging
import os
import sys
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
    cli,
    metrics,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.plugins import deepgram, groq, cartesia, silero
from livekit.agents import ChatContext, ChatMessage

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
    
    # Get configuration from room metadata if available
    room_metadata = ctx.room.metadata or "{}"
    logger.info(f"RAW Room Metadata: {room_metadata}")
    
    # Parse metadata for custom instructions
    instructions = None
    stt_model = "deepgram/nova-3-general"#"assemblyai/universal-streaming:en"
    llm_model = "openai/gpt-4.1-mini"
    tts_model = "cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
    
    try:
        import json
        metadata = json.loads(room_metadata)
        instructions = metadata.get("instructions")
        stt_model = metadata.get("stt_model", stt_model)
        llm_model = metadata.get("llm_model", llm_model)
        tts_model = metadata.get("tts_model", tts_model)
    except Exception as e:
        logger.warning(f"Could not parse room metadata: {e}")

    # Check for Riddler/Moriarty persona trigger
    if instructions is None and "crime_type" in metadata or "riddler" in str(metadata).lower():
        logger.info("Activating Riddler/Moriarty Persona")
        instructions = get_criminal_mindset_prompt(metadata)

    
    # Initialize usage collector for metrics
    usage_collector = metrics.UsageCollector()
    
    # Create agent session with configured models
    session = AgentSession(
        stt=stt_model,#"assemblyai/universal-streaming:en"
        llm="openai/gpt-4.1-mini",
        tts=tts_model,
        preemptive_generation=True,  # Generate responses while user is speaking
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
    await session.say(
   "Hello. How can I help you today?",
   allow_interruptions=True,
)
    logger.info(f"Agent successfully started in room: {ctx.room.name}")


if __name__ == "__main__":
    # Run the agent worker
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )