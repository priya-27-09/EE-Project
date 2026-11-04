"""
Geocoding & Place Search Service for AI Civic Guardian.
Provides place search, address resolution, coordinate extraction, and reverse geocoding
with special focus on Coimbatore Municipal Corporation area and Tamil Nadu localities.
"""

import os
import re
import json
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Center of Coimbatore Corporation
COIMBATORE_DEFAULT_LAT = 11.0168
COIMBATORE_DEFAULT_LON = 76.9558

# Comprehensive curated Coimbatore Gazetteer for fast, offline-capable, and precise local landmark matches
COIMBATORE_GAZETTEER = [
    # Central Zone & Hubs
    {
        "place_name": "Gandhipuram",
        "display_name": "Gandhipuram Central Hub, Coimbatore, Tamil Nadu, 641012, India",
        "latitude": 11.0183,
        "longitude": 76.9644,
        "locality": "Gandhipuram",
        "type": "central_hub",
        "keywords": ["gandhipuram", "cross cut", "crosscut", "100 feet", "hundred feet road", "power house"],
    },
    {
        "place_name": "Cross Cut Road, Gandhipuram",
        "display_name": "Cross Cut Road, Gandhipuram, Coimbatore, Tamil Nadu, 641012, India",
        "latitude": 11.0195,
        "longitude": 76.9658,
        "locality": "Gandhipuram",
        "type": "arterial_road",
        "keywords": ["cross cut", "crosscut", "cross cut road", "gandhipuram shopping"],
    },
    {
        "place_name": "Town Hall / Ukkadam",
        "display_name": "Town Hall, Central Coimbatore, Tamil Nadu, 641001, India",
        "latitude": 10.9925,
        "longitude": 76.9614,
        "locality": "Town Hall",
        "type": "heritage_center",
        "keywords": ["town hall", "ukkadam", "clock tower", "manikoondu", "oppanakara", "big bazaar"],
    },
    {
        "place_name": "RS Puram",
        "display_name": "R.S. Puram, West Zone, Coimbatore, Tamil Nadu, 641002, India",
        "latitude": 11.0116,
        "longitude": 76.9472,
        "locality": "RS Puram",
        "type": "residential_commercial",
        "keywords": ["rs puram", "r.s. puram", "rathinasabapathy", "db road", "diwan bahadur"],
    },
    {
        "place_name": "DB Road, RS Puram",
        "display_name": "Diwan Bahadur Road (DB Road), RS Puram, Coimbatore, Tamil Nadu, 641002, India",
        "latitude": 11.0125,
        "longitude": 76.9480,
        "locality": "RS Puram",
        "type": "arterial_road",
        "keywords": ["db road", "diwan bahadur road"],
    },
    {
        "place_name": "Peelamedu",
        "display_name": "Peelamedu, East Zone, Coimbatore, Tamil Nadu, 641004, India",
        "latitude": 11.0315,
        "longitude": 77.0050,
        "locality": "Peelamedu",
        "type": "education_hub",
        "keywords": ["peelamedu", "psg", "coimbatore airport", "civil aerodrome", "fun mall", "hope college"],
    },
    {
        "place_name": "Saibaba Colony",
        "display_name": "Saibaba Colony, North-West Zone, Coimbatore, Tamil Nadu, 641011, India",
        "latitude": 11.0321,
        "longitude": 76.9416,
        "locality": "Saibaba Colony",
        "type": "residential_commercial",
        "keywords": ["saibaba colony", "nsr road", "sai baba"],
    },
    {
        "place_name": "Singanallur",
        "display_name": "Singanallur, East Zone, Coimbatore, Tamil Nadu, 641005, India",
        "latitude": 10.9991,
        "longitude": 77.0267,
        "locality": "Singanallur",
        "type": "transit_hub",
        "keywords": ["singanallur", "singanallur bus stand", "singanallur lake", "trichy road"],
    },
    {
        "place_name": "Ramanathapuram",
        "display_name": "Ramanathapuram, Central-East, Coimbatore, Tamil Nadu, 641045, India",
        "latitude": 11.0028,
        "longitude": 76.9882,
        "locality": "Ramanathapuram",
        "type": "residential_commercial",
        "keywords": ["ramanathapuram", "trichy road ramanathapuram", "sungam"],
    },
    {
        "place_name": "Vadavalli",
        "display_name": "Vadavalli, West Zone, Coimbatore, Tamil Nadu, 641041, India",
        "latitude": 11.0266,
        "longitude": 76.9038,
        "locality": "Vadavalli",
        "type": "residential",
        "keywords": ["vadavalli", "marudhamalai road", "marudamalai"],
    },
    {
        "place_name": "Saravanampatti",
        "display_name": "Saravanampatti IT Corridor, North Zone, Coimbatore, Tamil Nadu, 641035, India",
        "latitude": 11.0827,
        "longitude": 76.9976,
        "locality": "Saravanampatti",
        "type": "tech_corridor",
        "keywords": ["saravanampatti", "chill sezone", "kct", "kumaraguru", "sathy road"],
    },
    {
        "place_name": "Thudiyalur",
        "display_name": "Thudiyalur, North Zone, Coimbatore, Tamil Nadu, 641034, India",
        "latitude": 11.0815,
        "longitude": 76.9388,
        "locality": "Thudiyalur",
        "type": "commercial_suburb",
        "keywords": ["thudiyalur", "mettupalayam road", "vellakinar"],
    },
    {
        "place_name": "Kuniyamuthur",
        "display_name": "Kuniyamuthur, South-West Zone, Coimbatore, Tamil Nadu, 641008, India",
        "latitude": 10.9566,
        "longitude": 76.9538,
        "locality": "Kuniyamuthur",
        "type": "residential",
        "keywords": ["kuniyamuthur", "palakkad road", "sri krishna college"],
    },
    {
        "place_name": "Kurichi / Sundarapuram",
        "display_name": "Sundarapuram, South Zone, Coimbatore, Tamil Nadu, 641024, India",
        "latitude": 10.9412,
        "longitude": 76.9745,
        "locality": "Sundarapuram",
        "type": "industrial_residential",
        "keywords": ["sundarapuram", "kurichi", "pollachi road"],
    },
    {
        "place_name": "Koundampalayam",
        "display_name": "Koundampalayam, North-West, Coimbatore, Tamil Nadu, 641030, India",
        "latitude": 11.0456,
        "longitude": 76.9298,
        "locality": "Koundampalayam",
        "type": "residential",
        "keywords": ["koundampalayam", "edayarpalayam"],
    },
    {
        "place_name": "Ganapathy",
        "display_name": "Ganapathy, Central-North, Coimbatore, Tamil Nadu, 641006, India",
        "latitude": 11.0378,
        "longitude": 76.9754,
        "locality": "Ganapathy",
        "type": "residential_industrial",
        "keywords": ["ganapathy", "athipalayam pirivu", "sathy road ganapathy"],
    },
    {
        "place_name": "SITRA / Coimbatore Airport",
        "display_name": "SITRA, Civil Aerodrome Post, Coimbatore, Tamil Nadu, 641014, India",
        "latitude": 11.0370,
        "longitude": 77.0426,
        "locality": "SITRA",
        "type": "transit_hub",
        "keywords": ["sitra", "airport", "coimbatore international airport", "civil aerodrome", "avanshi road airport"],
    },
    {
        "place_name": "Ondipudur",
        "display_name": "Ondipudur, South-East Zone, Coimbatore, Tamil Nadu, 641016, India",
        "latitude": 10.9880,
        "longitude": 77.0540,
        "locality": "Ondipudur",
        "type": "residential_suburb",
        "keywords": ["ondipudur", "trichy road ondipudur", "irugur"],
    },
    {
        "place_name": "Race Course",
        "display_name": "Race Course Promenade, Central Zone, Coimbatore, Tamil Nadu, 641018, India",
        "latitude": 11.0062,
        "longitude": 76.9723,
        "locality": "Race Course",
        "type": "recreational_promenade",
        "keywords": ["race course", "racecourse", "collectorate", "thomas park"],
    },
    {
        "place_name": "Coimbatore Junction Railway Station",
        "display_name": "Coimbatore Railway Junction, State Bank Road, Gopalapuram, Coimbatore, Tamil Nadu, 641018, India",
        "latitude": 10.9982,
        "longitude": 76.9634,
        "locality": "Gopalapuram",
        "type": "railway_station",
        "keywords": ["railway station", "railway junction", "coimbatore junction", "cbe junction", "train station"],
    },
    {
        "place_name": "Brookefields Mall",
        "display_name": "Brookefields Mall, Krishnaswamy Road, Sukrawar Pettai, Coimbatore, Tamil Nadu, 641001, India",
        "latitude": 11.0080,
        "longitude": 76.9585,
        "locality": "Sukrawar Pettai",
        "type": "shopping_landmark",
        "keywords": ["brookefields", "brookfields", "brookfield mall", "krishnaswamy road"],
    },
    {
        "place_name": "Avinashi Road",
        "display_name": "Avinashi Road (NH 544), Coimbatore, Tamil Nadu, India",
        "latitude": 11.0250,
        "longitude": 76.9950,
        "locality": "East Zone",
        "type": "major_highway",
        "keywords": ["avinashi road", "avinashi", "flyover", "laxmi mills"],
    },
    {
        "place_name": "Mettupalayam Road",
        "display_name": "Mettupalayam Road (NH 181), Coimbatore, Tamil Nadu, India",
        "latitude": 11.0500,
        "longitude": 76.9350,
        "locality": "North Zone",
        "type": "major_highway",
        "keywords": ["mettupalayam road", "mtp road"],
    },
    {
        "place_name": "Trichy Road",
        "display_name": "Trichy Road (SH 162), Coimbatore, Tamil Nadu, India",
        "latitude": 10.9950,
        "longitude": 77.0100,
        "locality": "South-East Zone",
        "type": "major_highway",
        "keywords": ["trichy road", "sungam bypass"],
    },
    {
        "place_name": "Perur Temple",
        "display_name": "Perur Pateeswarar Temple, Perur, Coimbatore, Tamil Nadu, 641010, India",
        "latitude": 10.9708,
        "longitude": 76.9142,
        "locality": "Perur",
        "type": "heritage_landmark",
        "keywords": ["perur", "pateeswarar", "perur temple", "noyyal river"],
    },
    {
        "place_name": "Marudhamalai Temple",
        "display_name": "Subramanyaswami Temple, Marudhamalai, Coimbatore, Tamil Nadu, 641046, India",
        "latitude": 11.0458,
        "longitude": 76.8525,
        "locality": "Marudhamalai",
        "type": "heritage_landmark",
        "keywords": ["marudhamalai", "marudamalai", "murugan temple"],
    },
]


class GeocodingService:
    """Service to handle location search, geocoding, and reverse geocoding."""

    @classmethod
    def search_local_gazetteer(cls, query: str) -> List[Dict[str, Any]]:
        """Search curated local gazetteer for matching landmarks and localities."""
        q_norm = re.sub(r"[^\w\s]", " ", query.lower()).strip()
        tokens = [t for t in q_norm.split() if t and t not in ("coimbatore", "tamil", "nadu", "india", "in", "near", "at")]
        if not tokens and ("coimbatore" in q_norm or "cbe" in q_norm):
            tokens = ["gandhipuram"]

        matches = []
        for entry in COIMBATORE_GAZETTEER:
            score = 0
            name_norm = entry["place_name"].lower()
            disp_norm = entry["display_name"].lower()
            keywords = entry.get("keywords", [])

            # Exact or phrase match
            if q_norm in name_norm or q_norm in disp_norm:
                score += 10
            for kw in keywords:
                if kw in q_norm or q_norm in kw:
                    score += 8
                for t in tokens:
                    if t in kw:
                        score += 3

            for t in tokens:
                if t in name_norm:
                    score += 4
                elif t in disp_norm:
                    score += 2

            if score > 0:
                matches.append((score, {
                    "place_name": entry["place_name"],
                    "display_name": entry["display_name"],
                    "latitude": round(entry["latitude"], 6),
                    "longitude": round(entry["longitude"], 6),
                    "locality": entry.get("locality"),
                    "city": "Coimbatore",
                    "type": entry.get("type", "landmark"),
                }))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:6]]

    @classmethod
    def query_photon_api(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Query Photon OSM geocoding API with Coimbatore bias."""
        results = []
        try:
            # Append Coimbatore to query if not already present to ensure focused results
            q_clean = query.strip()
            if "coimbatore" not in q_clean.lower() and "tamil nadu" not in q_clean.lower():
                q_param = f"{q_clean}, Coimbatore"
            else:
                q_param = q_clean

            url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(q_param)}&lat={COIMBATORE_DEFAULT_LAT}&lon={COIMBATORE_DEFAULT_LON}&limit={limit}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AI-Civic-Guardian/1.0 (Municipal Grievance Platform; Coimbatore)"},
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    features = payload.get("features", [])
                    for feat in features:
                        coords = feat.get("geometry", {}).get("coordinates", [])
                        if len(coords) >= 2:
                            lon, lat = float(coords[0]), float(coords[1])
                            props = feat.get("properties", {})
                            name = props.get("name") or props.get("street") or q_clean
                            city = props.get("city") or props.get("district") or "Coimbatore"
                            state = props.get("state") or "Tamil Nadu"
                            postcode = props.get("postcode")
                            
                            display_parts = [name]
                            if props.get("street") and props.get("street") != name:
                                display_parts.append(props.get("street"))
                            if city:
                                display_parts.append(city)
                            if state:
                                display_parts.append(state)
                            if postcode:
                                display_parts.append(str(postcode))
                            display_parts.append("India")

                            results.append({
                                "place_name": name,
                                "display_name": ", ".join(display_parts),
                                "latitude": round(lat, 6),
                                "longitude": round(lon, 6),
                                "locality": props.get("district") or props.get("suburb") or city,
                                "city": city,
                                "type": props.get("osm_value") or "osm_place",
                            })
        except Exception as exc:
            logger.debug(f"Photon API call skipped/failed: {exc}")

        return results

    @classmethod
    def query_nominatim_api(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Query Nominatim with strict server-side User-Agent and short timeout."""
        results = []
        try:
            q_clean = query.strip()
            if "coimbatore" not in q_clean.lower():
                q_param = f"{q_clean}, Coimbatore, Tamil Nadu, India"
            else:
                q_param = q_clean

            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q_param)}&format=json&limit={limit}&addressdetails=1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AI-Civic-Guardian/1.0 (civic.portal.redressal@internal)"},
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for item in data:
                        lat = float(item["lat"])
                        lon = float(item["lon"])
                        addr = item.get("address", {})
                        name = (
                            item.get("name")
                            or addr.get("suburb")
                            or addr.get("road")
                            or addr.get("neighbourhood")
                            or q_clean
                        )
                        results.append({
                            "place_name": name,
                            "display_name": item.get("display_name", f"{name}, Coimbatore, Tamil Nadu"),
                            "latitude": round(lat, 6),
                            "longitude": round(lon, 6),
                            "locality": addr.get("suburb") or addr.get("neighbourhood") or "Coimbatore",
                            "city": addr.get("city") or "Coimbatore",
                            "type": item.get("type", "address"),
                        })
        except Exception as exc:
            logger.debug(f"Nominatim fallback call skipped/failed: {exc}")

        return results

    @classmethod
    def query_apikey_provider(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Query an API-key-managed geocoding provider (e.g. LocationIQ)
        if configured via environment variable GEOCODING_API_KEY or LOCATIONIQ_API_KEY.
        Never breaks or fails if key is not configured.
        """
        api_key = os.getenv("GEOCODING_API_KEY") or os.getenv("LOCATIONIQ_API_KEY")
        if not api_key:
            return []

        results = []
        try:
            q_clean = query.strip()
            if "coimbatore" not in q_clean.lower() and "tamil nadu" not in q_clean.lower():
                q_param = f"{q_clean}, Coimbatore, Tamil Nadu, India"
            else:
                q_param = q_clean

            url = f"https://us1.locationiq.com/v1/search?key={urllib.parse.quote(api_key)}&q={urllib.parse.quote(q_param)}&format=json&limit={limit}&addressdetails=1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AI-Civic-Guardian/1.0 (Municipal Grievance Platform)"},
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for item in data:
                        try:
                            lat = float(item["lat"])
                            lon = float(item["lon"])
                        except (ValueError, TypeError, KeyError):
                            continue
                        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                            continue
                        addr = item.get("address", {})
                        name = (
                            item.get("display_name", "").split(",")[0].strip()
                            or addr.get("suburb")
                            or addr.get("road")
                            or q_clean
                        )
                        results.append({
                            "place_name": name,
                            "display_name": item.get("display_name", f"{name}, Coimbatore, Tamil Nadu"),
                            "latitude": round(lat, 6),
                            "longitude": round(lon, 6),
                            "locality": addr.get("suburb") or addr.get("neighbourhood") or "Coimbatore",
                            "city": addr.get("city") or "Coimbatore",
                            "type": item.get("type", "address"),
                        })
        except Exception as exc:
            logger.debug(f"API key geocoding provider query skipped or failed: {exc}")

        return results

    @classmethod
    def search_location(cls, query: str) -> List[Dict[str, Any]]:
        """
        Unified search for a place name or landmark:
        Combines local gazetteer matching with external geocoding providers.
        Ensures valid coordinate verification (-90 to 90, -180 to 180) and deduplication.
        """
        clean_q = (query or "").strip()
        if not clean_q or len(clean_q) < 2:
            return []

        # 1. Local Gazetteer matches (Instant, reliable, Coimbatore-tailored)
        local_matches = cls.search_local_gazetteer(clean_q)

        # 2. Key-based Provider matches (if configured via env)
        apikey_matches = cls.query_apikey_provider(clean_q)

        # 3. External Provider matches (Photon first, then Nominatim server-side)
        external_matches = cls.query_photon_api(clean_q)
        if not external_matches:
            external_matches = cls.query_nominatim_api(clean_q)

        # 4. Merge & Deduplicate
        all_candidates = []
        seen_coords = set()

        for item in local_matches + apikey_matches + external_matches:
            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                continue
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                continue

            # Deduplicate by ~200m grid
            coord_key = (round(lat_f, 3), round(lon_f, 3))
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)
            all_candidates.append(item)

        return all_candidates[:6]

    @classmethod
    def reverse_geocode(cls, lat: float, lon: float) -> Dict[str, Any]:
        """
        Reverse geocodes coordinates to a readable place name and address.
        Uses distance to closest known Coimbatore landmark and Corporation zone.
        """
        from app.services.boundary_service import CoimbatoreBoundaryService, COIMBATORE_LOCALITIES

        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return {
                "place_name": "Custom Coordinates",
                "display_name": f"Coordinates ({lat:.6f}, {lon:.6f})",
                "locality": None,
                "city": "Coimbatore",
            }

        # Find closest locality in Coimbatore
        nearest_loc, nearest_dist = CoimbatoreBoundaryService.find_nearest_locality_with_dist(lat, lon)
        
        # Check against gazetteer for fine-grained landmarks within 500m
        best_landmark = None
        min_lm_dist = float("inf")
        for entry in COIMBATORE_GAZETTEER:
            d_lat = lat - entry["latitude"]
            d_lon = lon - entry["longitude"]
            dist_approx = (d_lat**2 + d_lon**2)**0.5 * 111000  # meters
            if dist_approx < min_lm_dist:
                min_lm_dist = dist_approx
                best_landmark = entry

        if best_landmark and min_lm_dist < 400:
            place_name = best_landmark["place_name"]
            display_name = f"{place_name}, {nearest_loc}, Coimbatore, Tamil Nadu, India"
            locality = nearest_loc
        elif nearest_loc:
            place_name = nearest_loc
            display_name = f"{nearest_loc}, Coimbatore, Tamil Nadu, India"
            locality = nearest_loc
        else:
            place_name = f"Location ({lat:.4f}, {lon:.4f})"
            display_name = f"Coimbatore Municipal Area ({lat:.6f}, {lon:.6f})"
            locality = "Coimbatore"

        return {
            "place_name": place_name,
            "display_name": display_name,
            "locality": locality,
            "city": "Coimbatore",
            "distance_meters": round(min_lm_dist if best_landmark else nearest_dist, 1),
        }
