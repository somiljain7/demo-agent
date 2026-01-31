import os
import asyncio
from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def check_room_status(room_name):
    print(f"Connecting to LiveKit API to check room '{room_name}'...")
    lkapi = api.LiveKitAPI(
        os.getenv('LIVEKIT_URL'),
        os.getenv('LIVEKIT_API_KEY'),
        os.getenv('LIVEKIT_API_SECRET'),
    )
    
    try:
        # Check if room exists
        results = await lkapi.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
        
        if not results.rooms:
            print(f"❌ Room '{room_name}' is currently INACTIVE (does not exist).")
            print("👉 The agent will only join when a user creates the room by connecting to it.")
            return

        room = results.rooms[0]
        print(f"✅ Room '{room.name}' is ACTIVE.")
        print(f"   SID: {room.sid}")
        print(f"   Participants: {room.num_participants}")
        
        # List participants
        participants = await lkapi.room.list_participants(api.ListParticipantsRequest(room=room_name))
        print("\n📋 Participant List:")
        agent_found = False
        for p in participants.participants:
            role = "Agent" if p.kind == api.ParticipantInfo.Kind.AGENT else "User"
            if "agent" in p.identity.lower() or "agent" in p.name.lower():
                role = "Agent (Probable)"
                agent_found = True
                
            print(f"   - {p.identity} ({p.name}) [{role}] - State: {p.state}")
            
        if agent_found:
            print("\n✅ Agent IS present in the room.")
        else:
            print("\n⚠️ Agent is NOT found in the participant list yet.")
            
    except Exception as e:
        print(f"Error querying LiveKit API: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(check_room_status("chut"))
