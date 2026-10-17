"""Configuración común de las pruebas.

``logica.py`` no importa nada de HA: se carga directo desde su carpeta para poder
probarlo con un ``pytest`` cualquiera, sin instalar Home Assistant.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "facturas"))
