"""La historia larga: el registro de HA guarda estadísticas de los sensores de importes (Fase 5)."""

from datetime import timedelta

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.recorder.statistics import (  # noqa: E402
    async_list_statistic_ids,
    statistics_during_period,
)
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.util import dt as dt_util  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402
from pytest_homeassistant_custom_component.components.recorder.common import (  # noqa: E402
    async_wait_recording_done,
    do_adhoc_statistics,
)

from custom_components.facturas.const import DOMAIN  # noqa: E402


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Como el del conftest, pero con el recorder antes que hass (si no, su base no se prepara)."""
    yield


async def test_sensores_en_la_historia_larga(recorder_mock, hass: HomeAssistant) -> None:
    """Los sensores de importes entran en la historia larga (la fecha del próximo vencimiento, no)."""
    entrada = MockConfigEntry(domain=DOMAIN, title="Facturas", options={"moneda_principal": "pesos", "dias_aviso": 3})
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(DOMAIN, "agregar_servicio", {"nombre": "UTE", "importe": 1500}, blocking=True)
    await hass.services.async_call(DOMAIN, "registrar_pago", {"servicio": "ute", "importe": 1490}, blocking=True)
    await async_wait_recording_done(hass)

    ids = {s["statistic_id"]: s for s in await async_list_statistic_ids(hass)}
    for sensor in ("mes_previsto", "mes_pagado", "mes_falta", "anio_pagado"):
        assert f"sensor.facturas_{sensor}" in ids
        assert ids[f"sensor.facturas_{sensor}"]["statistics_unit_of_measurement"] == "UYU"
    assert "sensor.facturas_proxima" not in ids

    # Una compilación de 5 minutos genera filas para los sensores.
    inicio = dt_util.utcnow().replace(minute=(dt_util.utcnow().minute // 5) * 5, second=0, microsecond=0)
    do_adhoc_statistics(hass, start=inicio)
    await async_wait_recording_done(hass)
    filas = await hass.async_add_executor_job(
        statistics_during_period, hass, inicio - timedelta(minutes=5), None,
        {"sensor.facturas_mes_pagado"}, "5minute", None, {"state", "sum"},
    )
    assert filas["sensor.facturas_mes_pagado"][0]["state"] == 1490
