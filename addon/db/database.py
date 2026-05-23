import os, sys
sys.path.insert(0, '/opt/xhttp-manager/addon')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import toml

config_path = os.environ.get('XHTTP_MANAGER_CONFIG', '/etc/xhttp-manager/config.toml')
if os.path.exists(config_path):
    config = toml.load(config_path)
    db_path = config.get('storage', {}).get('db_path', '/var/lib/xhttp-manager/db.sqlite')
else:
    db_path = '/var/lib/xhttp-manager/db.sqlite'

os.makedirs(os.path.dirname(db_path), exist_ok=True)
DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    from db.models import User, AuditLog, Setting
    Base.metadata.create_all(bind=engine)
