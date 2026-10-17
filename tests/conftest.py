"""Configuración común de las pruebas.

``logica.py`` no importa nada de HA: se carga directo desde su carpeta para poder
probarlo con un ``pytest`` cualquiera, sin instalar Home Assistant. Las pruebas de la
integración necesitan ``pytest-homeassistant-custom-component`` (ver Dockerfile.pruebas)
y se saltean si no está.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "facturas"))

try:
    import pytest_homeassistant_custom_component  # noqa: F401
except ImportError:
    pass
else:

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Permite cargar las integraciones de custom_components/ en todas las pruebas."""
        yield
