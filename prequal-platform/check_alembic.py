from alembic.config import Config
from alembic.script import ScriptDirectory
import os

cfg = Config(os.path.join(os.path.dirname(__file__), 'alembic.ini'))
scripts = ScriptDirectory.from_config(cfg)
revs = list(scripts.walk_revisions())
for s in revs:
    print(s.revision, '->', s.down_revision)
