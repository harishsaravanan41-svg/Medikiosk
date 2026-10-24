from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class ChatMessage:
    id: str
    sender: str  # "patient" or "ai"
    modality: str  # "text", "voice", "dual"
    text: str
    audio_url: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class Patient:
    id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    known_conditions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ChatSession:
    session_id: str
    patient_id: str = "P-GUEST"
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: List[ChatMessage] = field(default_factory=list)
    triage_summary: Optional[dict] = None
