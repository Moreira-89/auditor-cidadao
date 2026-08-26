import sys
from pathlib import Path

# A raiz do pacote é backend/, o mesmo diretório que o container usa como WORKDIR.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
