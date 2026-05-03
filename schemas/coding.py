"""
Coding-related Pydantic schemas
Defines data models for code execution API (Judge0 proxy)
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class CodeExecuteRequest(BaseModel):
    """Schema for code execution request"""
    source_code: str = Field(..., description="Source code to execute", min_length=1)
    language: Literal["python", "c", "cpp", "java"] = Field(
        default="python", description="Programming language"
    )
    stdin: str = Field(default="", description="Standard input for the program")

    class Config:
        json_schema_extra = {
            "example": {
                "source_code": "print('Hello, World!')",
                "language": "python",
                "stdin": ""
            }
        }


class ExecutionStatus(BaseModel):
    """Judge0 execution status"""
    id: int = Field(..., description="Status ID")
    description: str = Field(..., description="Status description")


class CodeExecuteResponse(BaseModel):
    """Schema for code execution response"""
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")
    compile_output: Optional[str] = Field(None, description="Compilation output (for compiled languages)")
    status: ExecutionStatus = Field(..., description="Execution status")
    time: Optional[str] = Field(None, description="Execution time in seconds")
    memory: Optional[int] = Field(None, description="Memory used in KB")

    class Config:
        json_schema_extra = {
            "example": {
                "stdout": "Hello, World!\n",
                "stderr": None,
                "compile_output": None,
                "status": {"id": 3, "description": "Accepted"},
                "time": "0.012",
                "memory": 3456
            }
        }
