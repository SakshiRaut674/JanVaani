"""
Voice Processing Service for Audio Input/Output
Handles speech-to-text, text-to-speech, and audio processing
"""

import os
import asyncio
from typing import Dict, Any, Optional
from io import BytesIO

# Note: These will be imported after installing dependencies
try:
    import speech_recognition as sr
    from gtts import gTTS
    import pygame
    from pydub import AudioSegment
except ImportError:
    print("Warning: Voice processing libraries not installed. Please install: speech_recognition gtts pygame pydub")
    sr = None
    gTTS = None
    pygame = None
    AudioSegment = None


class VoiceService:
    """Handles voice processing functionality"""
    
    def __init__(self):
        self.recognizer = None
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize voice recognition components"""
        if not sr:
            raise RuntimeError("Speech recognition libraries not installed")
            
        self.recognizer = sr.Recognizer()
        
        # Initialize pygame for audio playback
        if pygame:
            pygame.mixer.init()
            
        self.is_initialized = True
        print("✅ Voice Service initialized successfully")
    
    async def speech_to_text(self, audio_data: bytes, language: str = "en-IN") -> str:
        """Convert speech audio to text"""
        if not self.is_initialized:
            raise RuntimeError("VoiceService not initialized. Call initialize() first.")
            
        try:
            # Convert bytes to AudioFile
            audio_file = sr.AudioFile(BytesIO(audio_data))
            
            with audio_file as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Record the audio
                audio = self.recognizer.record(source)
            
            # Use Google Speech Recognition
            try:
                # Try Google Speech Recognition first
                text = self.recognizer.recognize_google(audio, language=language)
                print(f"🎤 Recognized speech: {text}")
                return text
                
            except sr.RequestError:
                # Fallback to offline recognition if available
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                    print(f"🎤 Recognized speech (offline): {text}")
                    return text
                except:
                    raise Exception("Speech recognition services unavailable")
                    
        except sr.UnknownValueError:
            raise Exception("Could not understand audio")
        except Exception as e:
            print(f"Error in speech recognition: {e}")
            raise Exception(f"Speech recognition failed: {str(e)}")
    
    async def text_to_speech(self, text: str, language: str = "en") -> bytes:
        """Convert text to speech audio"""
        if not gTTS:
            raise RuntimeError("Text-to-speech library not available")
            
        try:
            # Create gTTS object
            tts = gTTS(text=text, lang=language, slow=False)
            
            # Save to bytes buffer
            audio_buffer = BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # Convert to WAV format if needed
            if AudioSegment:
                audio_segment = AudioSegment.from_mp3(audio_buffer)
                wav_buffer = BytesIO()
                audio_segment.export(wav_buffer, format="wav")
                return wav_buffer.getvalue()
            else:
                return audio_buffer.getvalue()
                
        except Exception as e:
            print(f"Error in text-to-speech: {e}")
            raise Exception(f"Text-to-speech failed: {str(e)}")
    
    async def play_audio(self, audio_data: bytes):
        """Play audio data through speakers"""
        if not pygame:
            raise RuntimeError("Pygame not available for audio playback")
            
        try:
            # Save to temporary buffer
            audio_buffer = BytesIO(audio_data)
            
            # Load and play audio
            pygame.mixer.music.load(audio_buffer)
            pygame.mixer.music.play()
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"Error playing audio: {e}")
            raise Exception(f"Audio playback failed: {str(e)}")
    
    def validate_audio_format(self, audio_data: bytes) -> Dict[str, Any]:
        """Validate and get info about audio data"""
        if not AudioSegment:
            return {"valid": True, "message": "Audio validation not available"}
            
        try:
            # Try to load audio
            audio = AudioSegment.from_file(BytesIO(audio_data))
            
            return {
                "valid": True,
                "duration": len(audio) / 1000.0,  # Duration in seconds
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "format": "detected"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "message": "Invalid audio format"
            }
    
    async def process_audio_file(self, file_path: str) -> str:
        """Process audio file and return text"""
        try:
            with sr.AudioFile(file_path) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.record(source)
            
            text = self.recognizer.recognize_google(audio, language="en-IN")
            return text
            
        except Exception as e:
            raise Exception(f"Audio file processing failed: {str(e)}")


# Global voice service instance
voice_service = VoiceService()