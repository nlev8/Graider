"""
Configuration management for Graider backend.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
BACKEND_DIR = Path(__file__).parent

# User data directories
HOME_DIR = Path.home()
GRAIDER_CONFIG_DIR = HOME_DIR / ".graider_assignments"
RUBRIC_FILE = HOME_DIR / ".graider_rubric.json"
SETTINGS_FILE = HOME_DIR / ".graider_settings.json"
EMAIL_CONFIG_FILE = HOME_DIR / ".graider_email.json"

# Ensure config directory exists
GRAIDER_CONFIG_DIR.mkdir(exist_ok=True)

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Default folders (can be overridden by user settings)
DEFAULT_ASSIGNMENTS_FOLDER = str(HOME_DIR / "Downloads" / "Graider" / "Assignments")
DEFAULT_OUTPUT_FOLDER = str(HOME_DIR / "Downloads" / "Graider" / "Results")
DEFAULT_ROSTER_FILE = ""

# Server configuration
HOST = "0.0.0.0"
PORT = 3000
DEBUG = True

# Grading configuration
SUPPORTED_FILE_TYPES = ['.docx', '.doc', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.bmp']


class Config:
    """Application configuration class."""

    def __init__(self):
        self.assignments_folder = DEFAULT_ASSIGNMENTS_FOLDER
        self.output_folder = DEFAULT_OUTPUT_FOLDER
        self.roster_file = DEFAULT_ROSTER_FILE
        self.assignment_name = ""
        self.openai_api_key = OPENAI_API_KEY
        self.grading_period = "Q1"

    def to_dict(self):
        return {
            "assignments_folder": self.assignments_folder,
            "output_folder": self.output_folder,
            "roster_file": self.roster_file,
            "assignment_name": self.assignment_name,
            "openai_api_key": self.openai_api_key,
            "grading_period": self.grading_period,
        }

    def update(self, data: dict):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Global config instance
config = Config()
