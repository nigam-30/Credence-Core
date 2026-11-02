"""
Credence Core — Database Engine & Session Management (Core)
"""

import sys
import os

# Link to existing database engine implementation
import database as root_db

engine = root_db.engine
SessionFactory = root_db.SessionFactory
SessionLocal = root_db.SessionLocal
Base = root_db.Base
get_db = root_db.get_db
get_db_session = root_db.get_db_session
init_db = root_db.init_db
drop_db = root_db.drop_db
IS_POSTGRES = root_db.IS_POSTGRES
get_db_url = root_db.get_db_url
