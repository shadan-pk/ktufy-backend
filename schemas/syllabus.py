"""
Syllabus-related Pydantic schemas
Defines data models for syllabus browsing API
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any


class TicklistRequest(BaseModel):
    """Schema for AI ticklist (topics) generation request"""
    subject_code: str = Field(..., description="Subject code (e.g. CST201)")
    subject_name: str = Field(..., description="Subject name (e.g. Data Structures)")
    module_number: int = Field(..., description="Module number (1-5)")


class ModuleItem(BaseModel):
    """A module within a subject"""
    module_number: int = Field(..., description="Module number (1-5)")
    title: str = Field(..., description="Module title/name")
    hours: Optional[int] = Field(None, description="Teaching hours allocated")
    topics: List[str] = Field(default_factory=list, description="Topics covered in this module")


class BranchItem(BaseModel):
    """A branch/department"""
    code: str = Field(..., description="Branch code (e.g. CSE)")
    name: str = Field(..., description="Full branch name")
    subject_count: int = Field(0, description="Number of subjects in this branch")


class SubjectListItem(BaseModel):
    """Summary of a subject (for listing)"""
    name: str = Field(..., description="Subject name")
    code: str = Field(..., description="Subject code (e.g. CST302)")
    credits: Optional[int] = Field(None, description="Credit hours")
    semester: Optional[int] = Field(None, description="Semester number")
    module_count: int = Field(0, description="Number of modules")
    category: Optional[str] = Field(None, description="Subject category (e.g. PCC, PEC, OEC)")


class SubjectDetail(BaseModel):
    """Full subject detail with modules and topics"""
    subject_name: str = Field(..., description="Subject name")
    subject_code: str = Field(..., description="Subject code")
    credits: Optional[int] = Field(None, description="Credit hours")
    semester: Optional[int] = Field(None, description="Semester number")
    branch: Optional[str] = Field(None, description="Branch code")
    category: Optional[str] = Field(None, description="Subject category (e.g. PCC, PEC, OEC)")
    modules: List[ModuleItem] = Field(default_factory=list, description="Modules in this subject")
    course_outcomes: List[str] = Field(default_factory=list, description="Course outcomes (COs)")
    textbooks: List[str] = Field(default_factory=list, description="Recommended textbooks")
    references: List[str] = Field(default_factory=list, description="Reference materials")

    class Config:
        json_schema_extra = {
            "example": {
                "subject_name": "Data Structures",
                "subject_code": "CST 201",
                "credits": 4,
                "semester": 3,
                "branch": "CSE",
                "modules": [
                    {
                        "module_number": 1,
                        "title": "Basic Concepts of Data Structures",
                        "hours": 5,
                        "topics": ["Arrays", "Stacks", "Queues"]
                    }
                ],
                "course_outcomes": ["CO1: Understand basic data structures"],
                "textbooks": ["Data Structures Using C - Reema Thareja"],
                "references": []
            }
        }
