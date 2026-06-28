"""
Geocoder module for the iPhone Photo Manager.
Uses Nominatim API with coordinate deduplication and rate limiting.
"""

import logging
import time
import json
import reverse_geocoder as rg
import pycountry
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory cache for coordinates: (lat_round, lng_round) -> "Location String"
_geocode_cache = {}


def batch_reverse_geocode(coordinates: list[tuple[float, float]]) -> list[Optional[str]]:
    """Batch geocode a list of (latitude, longitude) tuples instantly using offline reverse_geocoder."""
    if not coordinates:
        return []

    locations = []
    
    # Extract unique coordinates to geocode
    to_geocode = []
    coord_keys = []
    for lat, lng in coordinates:
        if lat is None or lng is None:
            coord_keys.append(None)
            continue
            
        lat_r = round(lat, 2)
        lng_r = round(lng, 2)
        coord_key = (lat_r, lng_r)
        coord_keys.append(coord_key)
        
        if coord_key not in _geocode_cache:
            to_geocode.append(coord_key)
            # Add a placeholder to avoid duplicate queries in the same batch
            _geocode_cache[coord_key] = None

    if to_geocode:
        logger.info(f"Offline geocoding {len(to_geocode)} unique clusters...")
        # reverse_geocoder is incredibly fast and takes a list of tuples
        results = rg.search(to_geocode)
        
        for coord_key, res in zip(to_geocode, results):
            name = res.get('name', '')
            admin1 = res.get('admin1', '')
            admin2 = res.get('admin2', '')
            cc = res.get('cc', '')
            
            # Map country code to full country name
            country = cc
            if cc:
                try:
                    c = pycountry.countries.get(alpha_2=cc)
                    if c:
                        country = c.name
                except Exception:
                    pass
            
            # Build parts
            parts = []
            if name:
                parts.append(name)
            if admin2 and admin2 != name:
                parts.append(admin2)
            if admin1 and admin1 != admin2 and admin1 != name:
                parts.append(admin1)
            if country:
                parts.append(country)
                
            loc_str = ", ".join(parts)
            _geocode_cache[coord_key] = loc_str
            logger.info("Geocoded %s -> %s", coord_key, loc_str)

    # Map back to original list
    for coord_key in coord_keys:
        if coord_key is None:
            locations.append(None)
        else:
            locations.append(_geocode_cache.get(coord_key))

    return locations


def reverse_geocode(latitude: float, longitude: float) -> Optional[str]:
    """Geocode a single coordinate."""
    return batch_reverse_geocode([(latitude, longitude)])[0]
