"""Optional deployment: marketplace at /, staff at /staff. uvicorn unified:app.

Requires both sets of dependencies/configuration. The staff standalone entry
point app.main:app is the entry point for the isolated local demo.
"""
from main import app
from app.main import app as staff_app

app.mount('/staff', staff_app)
