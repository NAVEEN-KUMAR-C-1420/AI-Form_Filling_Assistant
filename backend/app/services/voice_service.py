"""
Voice Input Service
Speech-to-text processing with user approval workflow
"""
import base64
import io
import tempfile
from typing import Dict, Optional, List
import speech_recognition as sr
from loguru import logger

from app.schemas.voice import VoiceInputResponse, SupportedLanguage


class VoiceInputService:
    """Service for voice input processing"""
    
    # Language code mapping for speech recognition
    LANGUAGE_CODES = {
        SupportedLanguage.ENGLISH: "en-IN",
        SupportedLanguage.HINDI: "hi-IN",
        SupportedLanguage.TAMIL: "ta-IN",
        SupportedLanguage.TELUGU: "te-IN",
        SupportedLanguage.KANNADA: "kn-IN",
        SupportedLanguage.MALAYALAM: "ml-IN"
    }
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Adjust for ambient noise
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
    
    async def process_voice_input(
        self,
        audio_data: str,
        language: SupportedLanguage,
        target_field: str
    ) -> VoiceInputResponse:
        """
        Process voice input and return recognized text
        Audio must be base64 encoded
        """
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Save to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            # Load audio file
            with sr.AudioFile(temp_path) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.record(source)
            
            # Get language code
            lang_code = self.LANGUAGE_CODES.get(language, "en-IN")
            
            # Recognize speech using Google Speech Recognition
            try:
                # Get main result
                result = self.recognizer.recognize_google(
                    audio,
                    language=lang_code,
                    show_all=True
                )
                
                if not result:
                    return VoiceInputResponse(
                        success=False,
                        recognized_text="",
                        confidence=0.0,
                        language_detected=lang_code,
                        alternatives=[],
                        requires_approval=True
                    )
                
                # Parse results
                if isinstance(result, dict) and 'alternative' in result:
                    alternatives = result['alternative']
                    main_result = alternatives[0]
                    
                    recognized_text = main_result.get('transcript', '')
                    confidence = main_result.get('confidence', 0.8)
                    
                    # Get alternative transcriptions
                    alt_texts = [
                        alt.get('transcript', '') 
                        for alt in alternatives[1:4]  # Get up to 3 alternatives
                        if alt.get('transcript')
                    ]
                    
                else:
                    recognized_text = str(result)
                    confidence = 0.8
                    alt_texts = []
                
                logger.info(f"Voice input recognized: '{recognized_text}' (confidence: {confidence})")
                
                return VoiceInputResponse(
                    success=True,
                    recognized_text=recognized_text,
                    confidence=round(confidence, 2),
                    language_detected=lang_code,
                    alternatives=alt_texts,
                    requires_approval=True  # Always require approval
                )
                
            except sr.UnknownValueError:
                logger.warning("Speech recognition could not understand audio")
                return VoiceInputResponse(
                    success=False,
                    recognized_text="",
                    confidence=0.0,
                    language_detected=lang_code,
                    alternatives=[],
                    requires_approval=True
                )
            
            except sr.RequestError as e:
                logger.error(f"Speech recognition request failed: {e}")
                raise ValueError(f"Speech recognition service unavailable: {e}")
                
        except Exception as e:
            logger.error(f"Voice input processing error: {e}", exc_info=True)
            raise ValueError(f"Failed to process voice input: {str(e)}")
        
        finally:
            # Clean up temp file
            import os
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
    
    def validate_audio_format(self, audio_data: str) -> bool:
        """Validate audio data format"""
        try:
            decoded = base64.b64decode(audio_data)
            # Check for WAV header
            if decoded[:4] == b'RIFF' and decoded[8:12] == b'WAVE':
                return True
            # Check for other common formats
            if decoded[:3] == b'ID3' or decoded[:2] == b'\xff\xfb':  # MP3
                return True
            return False
        except:
            return False
