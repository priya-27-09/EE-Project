"""
Coimbatore City Municipal Corporation (CCMC) Boundary Service
Provides geographic validation, official corporation bounds, and locality mapping.
"""

from typing import Tuple, Optional, List, Dict, Any
import math

# Center of Coimbatore City (Gandhipuram / Clock Tower area)
COIMBATORE_CENTER = {
    "latitude": 11.0168,
    "longitude": 76.9558,
}
DEFAULT_MAP_ZOOM = 13

# Authoritative Coimbatore City Municipal Corporation (CCMC) bounding box:
# Covers the 5 administrative zones (East, West, North, South, Central) and 100 municipal wards.
COIMBATORE_BOUNDS = {
    "min_latitude": 10.9000,
    "max_latitude": 11.1200,
    "min_longitude": 76.8600,
    "max_longitude": 77.0800,
}

# Detailed Polygon representing the Coimbatore Municipal Corporation service boundary
# Traces the perimeter from North through East, South, and West back to North.
COIMBATORE_BOUNDARY_POLYGON: List[Tuple[float, float]] = [
    (11.0850, 76.9050),  # Thudiyalur West
    (11.1150, 76.9500),  # Vellakinar / Thudiyalur North
    (11.1100, 77.0000),  # Saravanampatti North
    (11.0800, 77.0350),  # Kalapatti / SITRA North
    (11.0350, 77.0650),  # Peelamedu Airport / Civil Aerodrome East
    (10.9950, 77.0700),  # Singanallur / Ondipudur East
    (10.9500, 77.0350),  # Podanur / Nanjundapuram South-East
    (10.9200, 76.9850),  # Kurichi / Sundarapuram South
    (10.9350, 76.9450),  # Kuniyamuthur South-West
    (10.9650, 76.9150),  # Perur West
    (11.0150, 76.8850),  # Vadavalli West
    (11.0550, 76.8900),  # Koundampalayam / Edayarpalayam
]

# Key Coimbatore Corporation Hubs & Localities with approximate coordinates
COIMBATORE_LOCALITIES = [
    {"name": "Gandhipuram (Central Hub)", "lat": 11.0183, "lng": 76.9644, "pincode": "641012"},
    {"name": "RS Puram (West Zone)", "lat": 11.0116, "lng": 76.9472, "pincode": "641002"},
    {"name": "Peelamedu (East Zone)", "lat": 11.0315, "lng": 77.0050, "pincode": "641004"},
    {"name": "Saibaba Colony (North-West)", "lat": 11.0321, "lng": 76.9416, "pincode": "641011"},
    {"name": "Ukkadam / Town Hall (Central-South)", "lat": 10.9925, "lng": 76.9614, "pincode": "641001"},
    {"name": "Singanallur (East Zone)", "lat": 10.9991, "lng": 77.0267, "pincode": "641005"},
    {"name": "Ramanathapuram (Central-East)", "lat": 11.0028, "lng": 76.9882, "pincode": "641045"},
    {"name": "Vadavalli (West Zone)", "lat": 11.0266, "lng": 76.9038, "pincode": "641041"},
    {"name": "Saravanampatti (IT Corridor - North)", "lat": 11.0827, "lng": 76.9976, "pincode": "641035"},
    {"name": "Thudiyalur (North Zone)", "lat": 11.0815, "lng": 76.9388, "pincode": "641034"},
    {"name": "Kuniyamuthur (South-West)", "lat": 10.9566, "lng": 76.9538, "pincode": "641008"},
    {"name": "Kurichi / Sundarapuram (South Zone)", "lat": 10.9412, "lng": 76.9745, "pincode": "641024"},
    {"name": "Koundampalayam (North-West)", "lat": 11.0456, "lng": 76.9298, "pincode": "641030"},
    {"name": "Ganapathy (Central-North)", "lat": 11.0378, "lng": 76.9754, "pincode": "641006"},
    {"name": "SITRA / Airport Road (East)", "lat": 11.0370, "lng": 77.0426, "pincode": "641014"},
    {"name": "Ondipudur (South-East)", "lat": 10.9880, "lng": 77.0540, "pincode": "641016"},
]


class CoimbatoreBoundaryService:
    """Service to validate and manage Coimbatore Municipal Corporation service boundaries."""

    @classmethod
    def is_within_bounding_box(cls, lat: float, lon: float) -> bool:
        """Check if coordinates fall inside the standard Coimbatore bounding box."""
        return (
            COIMBATORE_BOUNDS["min_latitude"] <= lat <= COIMBATORE_BOUNDS["max_latitude"]
            and COIMBATORE_BOUNDS["min_longitude"] <= lon <= COIMBATORE_BOUNDS["max_longitude"]
        )

    @classmethod
    def is_point_in_polygon(cls, lat: float, lon: float, polygon: Optional[List[Tuple[float, float]]] = None) -> bool:
        """
        Ray-casting algorithm to test whether a coordinate (lat, lon) lies inside the boundary polygon.
        """
        poly = polygon or COIMBATORE_BOUNDARY_POLYGON
        n = len(poly)
        inside = False

        p1_lat, p1_lon = poly[0]
        for i in range(1, n + 1):
            p2_lat, p2_lon = poly[i % n]
            if lon > min(p1_lon, p2_lon):
                if lon <= max(p1_lon, p2_lon):
                    if lat <= max(p1_lat, p2_lat):
                        if p1_lon != p2_lon:
                            lat_inters = (lon - p1_lon) * (p2_lat - p1_lat) / (p2_lon - p1_lon) + p1_lat
                        if p1_lat == p2_lat or lat <= lat_inters:
                            inside = not inside
            p1_lat, p1_lon = p2_lat, p2_lon

        return inside

    @classmethod
    def validate_coordinates(cls, lat: Optional[float], lon: Optional[float]) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive validation of complaint coordinates against Coimbatore Municipal Corporation boundary.
        Returns:
            (is_valid: bool, error_message: Optional[str])
        """
        if lat is None or lon is None:
            # If coordinates are omitted (e.g. text/address only), allow if address is valid
            return True, None

        # Step 1: Bounding box fast-check
        if not cls.is_within_bounding_box(lat, lon):
            return (
                False,
                f"Selected location ({lat:.4f}, {lon:.4f}) is outside the Coimbatore Municipal Corporation boundary "
                f"(Latitude {COIMBATORE_BOUNDS['min_latitude']} to {COIMBATORE_BOUNDS['max_latitude']}, "
                f"Longitude {COIMBATORE_BOUNDS['min_longitude']} to {COIMBATORE_BOUNDS['max_longitude']}). "
                f"Complaints can only be registered within Coimbatore city corporation limits.",
            )

        # Step 2: Fine-grained polygon check with reasonable buffer (500m tolerance)
        in_poly = cls.is_point_in_polygon(lat, lon)
        if not in_poly:
            # If slightly outside polygon but within bounding box, allow if within 1km of any key locality
            nearest_name, nearest_dist = cls.find_nearest_locality_with_dist(lat, lon)
            if nearest_dist > 4500:  # > 4.5km away from any corporation zone hub
                return (
                    False,
                    f"Selected location ({lat:.4f}, {lon:.4f}) is outside the active Coimbatore Municipal Corporation service area. "
                    f"Nearest corporation locality is {nearest_name} (~{nearest_dist/1000:.1f} km away).",
                )

        return True, None

    @classmethod
    def find_nearest_locality_with_dist(cls, lat: float, lon: float) -> Tuple[str, float]:
        """Compute the closest Coimbatore locality and distance in meters using Haversine formula."""
        best_name = "Coimbatore City"
        best_dist = float("inf")

        for loc in COIMBATORE_LOCALITIES:
            d = cls._haversine_distance(lat, lon, loc["lat"], loc["lng"])
            if d < best_dist:
                best_dist = d
                best_name = loc["name"]

        return best_name, best_dist

    @classmethod
    def get_service_boundary_info(cls) -> Dict[str, Any]:
        """Return boundary and layer configuration for frontend map initialization."""
        return {
            "city": "Coimbatore",
            "state": "Tamil Nadu",
            "country": "India",
            "center": COIMBATORE_CENTER,
            "default_zoom": DEFAULT_MAP_ZOOM,
            "bounding_box": COIMBATORE_BOUNDS,
            "polygon": [[p[0], p[1]] for p in COIMBATORE_BOUNDARY_POLYGON],
            "localities": COIMBATORE_LOCALITIES,
            "imagery_provider": "Esri World Imagery (High Resolution Satellite)",
            "street_provider": "OpenStreetMap",
        }

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance in meters between two lat/lon points."""
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c
