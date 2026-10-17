"""Constantes de la integración Facturas."""

DOMAIN = "facturas"

# Opciones (config_flow)
OPCION_MONEDA = "moneda_principal"
OPCION_DIAS_AVISO = "dias_aviso"
MONEDA_PREDETERMINADA = "pesos"
DIAS_AVISO_PREDETERMINADOS = 3

# Se envía (dispatcher) cada vez que cambian los datos, para que las entidades se actualicen.
SENAL_ACTUALIZADO = f"{DOMAIN}_actualizado"

# Almacenamiento en .storage/facturas
CLAVE_ALMACEN = DOMAIN
VERSION_ALMACEN = 1
VERSION_MENOR_ALMACEN = 1
