import logging
import sys


def setup_logging():
    """Configura o formato de log padrão e o nível de verbosidade para a aplicação."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
