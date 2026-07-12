from ..config import api_url
from ..fetcher import fetch_units
from ..parser import parse_listings
from .base import Source, annotate_flags


class PrometheusSource(Source):
    """Prometheus Apartments internal JSON API (Spruce, Kensington Place, …)."""

    def fetch(self, prop: dict) -> list:
        return fetch_units(api_url(prop["property_id"]))

    def parse(self, raw_units: list) -> dict:
        units = parse_listings(raw_units)
        annotate_flags(units)
        return units
