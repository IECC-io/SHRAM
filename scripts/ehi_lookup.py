"""
EHI Lookup Table Module

Provides fast EHI and zone lookups using pre-computed tables.
No scipy or NumbaMinpack dependencies - just JSON files.

Tables are keyed by MET level and shortwave irradiance (SW in W/m²).
SW=0 corresponds to shade; higher SW values represent increasing solar load.

Usage:
    from ehi_lookup import EHILookup

    lookup = EHILookup()
    # SW-based lookup (new interface):
    ehi, zone = lookup.get_ehi_zone(temp_c=35.0, rh_percent=80, met_level=4, sw=400)
    # Legacy sun_condition interface still supported:
    ehi, zone = lookup.get_ehi_zone(temp_c=35.0, rh_percent=80, met_level=4, sun='shade')
"""

import json
import os

# Available SW irradiance levels in W/m²
SW_LEVELS = [0, 200, 400, 600, 800, 1000]

def snap_sw(sw_value):
    """Snap a SW irradiance value to the nearest available table level."""
    if sw_value is None or sw_value <= 0:
        return 0
    return min(SW_LEVELS, key=lambda x: abs(x - sw_value))


class EHILookup:
    """Fast EHI lookup using pre-computed tables."""

    def __init__(self, tables_dir=None):
        """
        Initialize the EHI lookup with pre-computed tables.

        Args:
            tables_dir: Directory containing the lookup table JSON files.
                       If None, looks in ./lookup_tables/ or ../lookup_tables/
        """
        if tables_dir is None:
            # Try to find tables directory
            possible_dirs = [
                os.path.join(os.path.dirname(__file__), 'lookup_tables'),
                os.path.join(os.path.dirname(__file__), '..', 'lookup_tables'),
                'lookup_tables',
                '../lookup_tables',
            ]
            for d in possible_dirs:
                if os.path.exists(d):
                    tables_dir = d
                    break
            else:
                raise FileNotFoundError("Could not find lookup_tables directory")

        self.tables_dir = tables_dir
        self.tables = {}
        self._load_tables()

    def _load_tables(self):
        """Load all lookup tables into memory."""
        met_levels = [3, 4, 5, 6]
        loaded = 0

        for met in met_levels:
            for sw in SW_LEVELS:
                key = f"met{met}_sw{sw}"
                filepath = os.path.join(self.tables_dir, f"ehi_{key}.json")

                if os.path.exists(filepath):
                    with open(filepath, 'r') as f:
                        self.tables[key] = json.load(f)
                    loaded += 1
                else:
                    print(f"Warning: Table not found: {filepath}")

        print(f"Loaded {loaded} EHI lookup tables")

    def get_ehi_zone(self, temp_c, rh_percent, met_level, sw=None, sun=None):
        """
        Get EHI and zone from lookup tables.

        Args:
            temp_c: Temperature in Celsius
            rh_percent: Relative humidity in percent (0-100)
            met_level: MET level (3, 4, 5, or 6)
            sw: Shortwave irradiance in W/m² (preferred). Snapped to nearest of
                [0, 200, 400, 600, 800, 1000].
            sun: Legacy sun condition ('shade' or 'sun'). If provided and sw is
                 None, maps shade→SW=0, sun→SW=800.

        Returns:
            (ehi, zone) tuple where ehi is in Celsius and zone is 1-6
        """
        # Resolve SW level
        if sw is not None:
            sw_level = snap_sw(sw)
        elif sun == 'shade':
            sw_level = 0
        elif sun == 'sun':
            sw_level = 800
        else:
            sw_level = 0

        key = f"met{met_level}_sw{sw_level}"

        if key not in self.tables:
            raise ValueError(f"No table loaded for {key}")

        table = self.tables[key]
        metadata = table['metadata']
        data = table['data']

        # Clamp temperature and humidity to table bounds
        temp_c = max(metadata['temp_min_c'], min(metadata['temp_max_c'], temp_c))
        rh_percent = max(metadata['rh_min_pct'], min(metadata['rh_max_pct'], rh_percent))

        # Round to nearest step
        temp_step = metadata['temp_step_c']
        rh_step = metadata['rh_step_pct']

        temp_rounded = round(temp_c / temp_step) * temp_step
        rh_rounded = int(round(rh_percent / rh_step) * rh_step)

        # Create keys
        temp_key = f"{temp_rounded:.1f}"
        rh_key = str(rh_rounded)

        # Lookup
        if temp_key in data and rh_key in data[temp_key]:
            result = data[temp_key][rh_key]
            return result[0], result[1]  # [ehi, zone]
        else:
            # Fallback: find nearest
            return self._find_nearest(data, temp_c, rh_percent)

    def _find_nearest(self, data, temp_c, rh_percent):
        """Find nearest entry if exact match not found."""
        temp_key = f"{round(temp_c * 2) / 2:.1f}"  # Round to 0.5
        rh_key = str(round(rh_percent))

        if temp_key in data:
            if rh_key in data[temp_key]:
                result = data[temp_key][rh_key]
                return result[0], result[1]
            # Try nearest humidity
            for offset in range(1, 10):
                for rh_try in [rh_key - offset, rh_key + offset]:
                    if str(rh_try) in data[temp_key]:
                        result = data[temp_key][str(rh_try)]
                        return result[0], result[1]

        return None, 0


# Global instance for convenience
_lookup_instance = None

def get_lookup():
    """Get or create the global EHI lookup instance."""
    global _lookup_instance
    if _lookup_instance is None:
        _lookup_instance = EHILookup()
    return _lookup_instance

def lookup_ehi_zone(temp_c, rh_percent, met_level, sw=None, sun=None):
    """
    Convenience function to look up EHI and zone.

    Args:
        temp_c: Temperature in Celsius
        rh_percent: Relative humidity in percent (0-100)
        met_level: MET level (3, 4, 5, or 6)
        sw: Shortwave irradiance in W/m² (preferred)
        sun: Legacy sun condition ('shade' or 'sun')

    Returns:
        (ehi, zone) tuple
    """
    return get_lookup().get_ehi_zone(temp_c, rh_percent, met_level, sw=sw, sun=sun)


# Also export constants used by other modules
cpc = 3492.0  # J/kg/K, specific heat capacity of body


if __name__ == '__main__':
    # Test the lookup
    lookup = EHILookup()

    print("\nTest lookups (SW-based):")
    test_cases_sw = [
        (30, 50, 3, 0),
        (35, 80, 4, 400),
        (40, 90, 5, 800),
        (45, 70, 6, 1000),
    ]
    for temp, rh, met, sw in test_cases_sw:
        ehi, zone = lookup.get_ehi_zone(temp, rh, met, sw=sw)
        print(f"  T={temp}°C, RH={rh}%, MET={met}, SW={sw}: EHI={ehi}°C, Zone={zone}")

    print("\nTest lookups (legacy sun/shade):")
    test_cases_legacy = [
        (30, 50, 3, 'shade'),
        (35, 80, 4, 'sun'),
    ]
    for temp, rh, met, sun in test_cases_legacy:
        ehi, zone = lookup.get_ehi_zone(temp, rh, met, sun=sun)
        print(f"  T={temp}°C, RH={rh}%, MET={met}, {sun}: EHI={ehi}°C, Zone={zone}")
