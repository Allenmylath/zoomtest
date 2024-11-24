import os
import jwt
import time
import json
import asyncio
import websockets
from datetime import datetime
from pydub import AudioSegment
from dotenv import load_dotenv
import requests

class ZoomAudioBot:
    def __init__(self):
        """Initialize Zoom bot with credentials from environment variables."""
        load_dotenv()
        
        # Zoom API credentials
        self.api_key = os.getenv('ZOOM_API_KEY')
        self.api_secret = os.getenv('ZOOM_API_SECRET')
        self.sdk_key = os.getenv('ZOOM_SDK_KEY')
        self.sdk_secret = os.getenv('ZOOM_SDK_SECRET')
        
        if not all([self.api_key, self.api_secret, self.sdk_key, self.sdk_secret]):
            raise ValueError("Missing required Zoom credentials in environment variables")
            
        self.base_url = "https://api.zoom.us/v2"
        self.ws_url = "wss://zoom.us/mpws"

    def _generate_jwt_token(self):
        """Generate JWT token for Zoom API authentication."""
        token = jwt.encode(
            {
                'iss': self.api_key,
                'exp': datetime.now().timestamp() + 5000
            },
            self.api_secret,
            algorithm='HS256'
        )
        return token

    async def _connect_to_meeting(self, meeting_id, password=None):
        """Connect to a Zoom meeting using WebSocket."""
        headers = {
            'Authorization': f'Bearer {self._generate_jwt_token()}',
            'Content-Type': 'application/json'
        }
        
        # Join meeting request
        join_data = {
            'meetingNumber': meeting_id,
            'role': 0,  # 0 for participant
            'sdkKey': self.sdk_key,
            'signature': self._generate_meeting_signature(meeting_id),
            'password': password if password else ''
        }
        
        async with websockets.connect(self.ws_url) as websocket:
            # Send join request
            await websocket.send(json.dumps({
                'action': 'join',
                'params': join_data
            }))
            
            # Handle meeting connection response
            response = await websocket.recv()
            return websocket if 'success' in response else None

    def _generate_meeting_signature(self, meeting_id):
        """Generate signature for joining a meeting."""
        timestamp = int(time.time() * 1000) - 30000
        msg = f'{self.sdk_key}{meeting_id}{timestamp}{1}'
        signature = jwt.encode(
            {'hash': msg},
            self.sdk_secret,
            algorithm='HS256'
        )
        return signature

    def _prepare_audio(self, mp3_path):
        """Convert MP3 to raw audio data for streaming."""
        audio = AudioSegment.from_mp3(mp3_path)
        return audio.raw_data

    async def play_audio_to_meeting(self, meeting_id, mp3_path, password=None):
        """Join a meeting and play an MP3 file."""
        try:
            print(f"Attempting to join meeting {meeting_id}...")
            websocket = await self._connect_to_meeting(meeting_id, password)
            
            if not websocket:
                print("Failed to connect to meeting")
                return
            
            print("Successfully joined meeting")
            print(f"Preparing to play: {mp3_path}")
            
            # Prepare audio data
            audio_data = self._prepare_audio(mp3_path)
            chunk_size = 1024 * 16  # 16KB chunks
            
            # Stream audio data
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                await websocket.send(json.dumps({
                    'action': 'audio',
                    'params': {
                        'data': chunk.hex()
                    }
                }))
                await asyncio.sleep(0.1)  # Control playback speed
                
            print("Finished playing audio")
            
        except Exception as e:
            print(f"Error during playback: {e}")
        
        finally:
            if websocket:
                await websocket.close()

def main():
    # Get meeting details from environment variables
    meeting_id = os.getenv('ZOOM_MEETING_ID')
    meeting_password = os.getenv('ZOOM_MEETING_PASSWORD')
    mp3_path = os.getenv('AUDIO_FILE_PATH')
    
    if not all([meeting_id, mp3_path]):
        print("Please set ZOOM_MEETING_ID and AUDIO_FILE_PATH environment variables")
        return
    
    bot = ZoomAudioBot()
    asyncio.run(bot.play_audio_to_meeting(meeting_id, mp3_path, meeting_password))

if __name__ == "__main__":
    main()
