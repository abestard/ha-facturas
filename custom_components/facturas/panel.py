"""El panel "Facturas" de la barra lateral (un único archivo JS, sin compilar ni librerías)."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration

from .const import DOMAIN

URL_PANEL = DOMAIN
URL_ARCHIVOS = f"/{DOMAIN}_panel"
ARCHIVO_JS = Path(__file__).parent / "panel" / "facturas-panel.js"
_RUTA_REGISTRADA = f"{DOMAIN}_ruta_panel"


async def registrar_panel(hass: HomeAssistant) -> None:
    # La ruta de archivos no se puede quitar: se registra una sola vez por arranque de HA.
    if not hass.data.get(_RUTA_REGISTRADA):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_ARCHIVOS, str(ARCHIVO_JS.parent), cache_headers=False)]
        )
        hass.data[_RUTA_REGISTRADA] = True
    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=URL_PANEL,
        webcomponent_name="facturas-panel",
        sidebar_title="Facturas",
        sidebar_icon="mdi:receipt-text-outline",
        # El ?v= hace que el navegador (y la app) bajen el JS nuevo al actualizar la integración.
        module_url=f"{URL_ARCHIVOS}/{ARCHIVO_JS.name}?v={version}",
        require_admin=True,
    )


@callback
def quitar_panel(hass: HomeAssistant) -> None:
    frontend.async_remove_panel(hass, URL_PANEL, warn_if_unknown=False)
