from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ClinicalFacts:
    chief_complaint: Optional[str] = None
    location: Optional[str] = None
    onset: Optional[str] = None
    character: Optional[str] = None
    severity: Optional[str] = None
    aggravating_factors: Optional[str] = None
    relieving_factors: Optional[str] = None
    associated_symptoms: List[str] = field(default_factory=list)
    urgency_level: str = "needs_assessment"

@dataclass
class EmergencyCheckResult:
    is_emergency: bool = False
    keyword_matched: Optional[str] = None
    urgency: Optional[str] = None
    department: Optional[str] = None

@dataclass
class TriageSummary:
    chief_complaint: str
    urgency_level: str
    urgency_color: str
    recommended_department: str
    emergency_flag: bool = False
    total_exchanges: int = 0
    location: Optional[str] = None
    onset: Optional[str] = None
    character: Optional[str] = None
    severity: Optional[str] = None
    aggravating_factors: Optional[str] = None
    relieving_factors: Optional[str] = None
    associated_symptoms: List[str] = field(default_factory=list)
