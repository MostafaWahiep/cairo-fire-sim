"""Cairo district definitions and default fire station locations."""

CAIRO_DISTRICTS = {
    "downtown": {
        "name": "Downtown",
        "center": (30.0444, 31.2357),
        "radius_km": 1.5,
        "population_density": 45000,
    },
    "zamalek": {
        "name": "Zamalek",
        "center": (30.0609, 31.2194),
        "radius_km": 1.0,
        "population_density": 30000,
    },
    "garden_city": {
        "name": "Garden City",
        "center": (30.0380, 31.2310),
        "radius_km": 0.8,
        "population_density": 25000,
    },
    "dokki": {
        "name": "Dokki",
        "center": (30.0382, 31.2118),
        "radius_km": 1.5,
        "population_density": 40000,
    },
    "mohandessin": {
        "name": "Mohandessin",
        "center": (30.0560, 31.2020),
        "radius_km": 1.5,
        "population_density": 38000,
    },
    "heliopolis": {
        "name": "Heliopolis",
        "center": (30.0866, 31.3222),
        "radius_km": 2.0,
        "population_density": 35000,
    },
    "nasr_city": {
        "name": "Nasr City",
        "center": (30.0511, 31.3411),
        "radius_km": 2.5,
        "population_density": 32000,
    },
    "maadi": {
        "name": "Maadi",
        "center": (30.0080, 31.2565),
        "radius_km": 2.0,
        "population_density": 20000,
    },
    "shubra": {
        "name": "Shubra",
        "center": (30.0850, 31.2441),
        "radius_km": 2.0,
        "population_density": 50000,
    },
    "giza_east": {
        "name": "Giza (East)",
        "center": (30.0131, 31.2089),
        "radius_km": 2.0,
        "population_density": 35000,
    },
    "old_cairo": {
        "name": "Old Cairo",
        "center": (30.0060, 31.2300),
        "radius_km": 1.2,
        "population_density": 42000,
    },
    "ain_shams": {
        "name": "Ain Shams",
        "center": (30.1100, 31.3230),
        "radius_km": 2.0,
        "population_density": 38000,
    },
    "abbassia": {
        "name": "Abbassia",
        "center": (30.0685, 31.2802),
        "radius_km": 1.5,
        "population_density": 35000,
    },
    "sayeda_zeinab": {
        "name": "Sayeda Zeinab",
        "center": (30.0290, 31.2490),
        "radius_km": 1.0,
        "population_density": 48000,
    },
    "hadayek_kobba": {
        "name": "Hadayek El-Kobba",
        "center": (30.0920, 31.2900),
        "radius_km": 1.5,
        "population_density": 42000,
    },
}

DEFAULT_STATIONS = {
    "s1": {
        "name": "Central Cairo Station",
        "lat": 30.0444,
        "lon": 31.2457,
    },
    "s2": {
        "name": "Heliopolis Station",
        "lat": 30.0866,
        "lon": 31.3222,
    },
    "s3": {
        "name": "Maadi Station",
        "lat": 30.0080,
        "lon": 31.2565,
    },
    "s4": {
        "name": "Dokki Station",
        "lat": 30.0382,
        "lon": 31.2118,
    },
    "s5": {
        "name": "Shubra Station",
        "lat": 30.0850,
        "lon": 31.2441,
    },
    "s6": {
        "name": "Nasr City Station",
        "lat": 30.0511,
        "lon": 31.3411,
    },
    "s7": {
        "name": "Giza Station",
        "lat": 30.0131,
        "lon": 31.2089,
    },
    "s8": {
        "name": "Abbassia Station",
        "lat": 30.0685,
        "lon": 31.2802,
    },
    "s9": {
        "name": "Old Cairo Station",
        "lat": 30.0100,
        "lon": 31.2350,
    },
    "s10": {
        "name": "Ain Shams Station",
        "lat": 30.1100,
        "lon": 31.3130,
    },
    "s11": {
        "name": "Mohandessin Station",
        "lat": 30.0560,
        "lon": 31.2020,
    },
    "s12": {
        "name": "Sayeda Zeinab Station",
        "lat": 30.0290,
        "lon": 31.2490,
    },
}
