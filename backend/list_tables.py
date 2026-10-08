from sqlalchemy import create_engine, text
from app.core.config import settings
e = create_engine(settings.database_url)
with e.connect() as c:
    r = c.execute(text('SELECT current_database(), current_user')).fetchone()
    print('db:', r)
    rows = c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")).fetchall()
    for x in rows:
        print(' ', x[0])