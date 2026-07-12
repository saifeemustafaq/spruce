from .base import Source
from .irvine import IrvineSource
from .prometheus import PrometheusSource

_SOURCES = {
    "prometheus": PrometheusSource,
    "irvine": IrvineSource,
}


def get_source(adapter_key: str) -> Source:
    cls = _SOURCES.get(adapter_key)
    if cls is None:
        raise ValueError(
            f"Unknown adapter '{adapter_key}'. Known adapters: "
            f"{', '.join(sorted(_SOURCES))}"
        )
    return cls()
