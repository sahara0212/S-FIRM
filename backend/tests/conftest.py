import os
import tempfile
from pathlib import Path

# 앱 import 시 init_db()·시드가 실행되므로, 개발용 DB 대신 임시 DB를 먼저 지정한다.
os.environ["SFIRM_DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp(prefix='sfirm-test-')) / 'test.db'}"
