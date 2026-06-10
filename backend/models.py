"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional


class Labs(BaseModel):
    hemoglobin:        Optional[float] = None   # g/dL
    ferritin:          Optional[float] = None   # ng/mL
    tsat:              Optional[float] = None   # %
    pth:               Optional[float] = None   # pg/mL
    calcium:           Optional[float] = None   # mg/dL
    phosphorus:        Optional[float] = None   # mg/dL
    vitamin_d_25oh:    Optional[float] = None   # ng/mL
    albumin:           Optional[float] = None   # g/dL
    bicarbonate:       Optional[float] = None   # mEq/L
    potassium:         Optional[float] = None   # mEq/L
    bun:               Optional[float] = None   # mg/dL
    creatinine:        Optional[float] = None   # mg/dL


class CurrentMedications(BaseModel):
    epo_dose_units_per_week:    Optional[float] = None
    darbepoetin_mcg_per_week:   Optional[float] = None
    iron_iv_active:             Optional[bool]  = None
    paricalcitol_mcg:           Optional[float] = None
    calcitriol_mcg:             Optional[float] = None
    cinacalcet_mg:              Optional[float] = None
    etelcalcetide_mg:           Optional[float] = None
    sevelamer_mg_tid:           Optional[float] = None
    calcium_acetate_mg_tid:     Optional[float] = None
    lanthanum_mg_tid:           Optional[float] = None


class PatientInput(BaseModel):
    patient_id:           str
    patient_name:         str = ""
    session_date:         str                        # YYYY-MM-DD
    labs:                 Labs
    current_medications:  CurrentMedications = Field(default_factory=CurrentMedications)
    prior_labs:           Optional[Labs] = None      # previous month, for trend display


class DeviationInput(BaseModel):
    patient_id:      str
    session_date:    str
    rule_id:         str
    protocol:        str
    rule_name:       str
    recommended:     list
    ordered:         str
    override_reason: str
    clinician_note:  str = ""


OVERRIDE_REASONS = [
    "Patient refused medication change",
    "Concern for hypercalcemia trend",
    "Concern for hypocalcemia / tetany risk",
    "Hemodynamic instability — ESA hold",
    "Active infection — ESA hold",
    "Iron overload concern",
    "Recent hospitalization — watchful waiting",
    "Insurance / formulary restriction",
    "Patient already self-adjusted dose",
    "Labs drawn off-schedule / timing artifact",
    "Planned procedure — hold medications",
    "Other (see clinician note)",
]
