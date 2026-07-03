"""Seed data for Kamdhenu Adhesives Comparison Tool.
Contains: Substrates, Tile Types, Kamdhenu Products (with full TDS specs),
Competitor brands & products, mapping logic.
"""

# 15 Substrates (from Excel "Substarte" sheet)
SUBSTRATES = [
    {"id": "concrete", "name": "Concrete", "description": "Composite construction material made of aggregate (sand, crushed stone, gravel) bound by hydraulic cement and water."},
    {"id": "cement_plaster", "name": "Cement Plaster", "description": "Homogeneous mix of Portland cement, fine aggregate, and water applied to concrete or brickwork for smooth finish."},
    {"id": "cement_screed", "name": "Cement Screed", "description": "Thin coating of specialized mortar (cement + sharp sand) applied over structural concrete to create a level surface."},
    {"id": "cement_mortar_beds", "name": "Cement Mortar Beds", "description": "Thick-bed (25-50mm) of cement and sand used as a sturdy foundation for tile/stone laying."},
    {"id": "brick_masonry", "name": "Brick Masonry", "description": "Bricks bonded by cement mortar in a systematic pattern. Durable structural system."},
    {"id": "plywood", "name": "Plywood", "description": "Engineered wood panel made by cross-graining glued veneers. Strong and stable."},
    {"id": "gypsum_boards", "name": "Gypsum Boards / Drywall", "description": "Manufactured panel of gypsum plaster sandwiched between paper sheets. Common for interior walls."},
    {"id": "cement_boards", "name": "Cement Boards / Backer Boards", "description": "Heavy-duty water-resistant board of Portland cement, water, and reinforcing fibers. Industry standard for wet areas."},
    {"id": "mdf", "name": "Medium-Density Fiberboard (MDF)", "description": "Engineered wood from fine fibers + wax/resin pressed at high temperature."},
    {"id": "calcium_silicate", "name": "Calcium Silicate Boards", "description": "High-performance autoclaved boards of siliceous materials and calcium oxide reinforced with cellulose fibers."},
    {"id": "metallic", "name": "Metallic Substrates", "description": "Steel, stainless steel, aluminum, copper surfaces."},
    {"id": "glass", "name": "Glass Substrates", "description": "Glass blocks, mirrored panels, or toughened glass sheets used as base for tile."},
    {"id": "terrazzo", "name": "Terrazzo", "description": "Composite of marble/quartz/granite chips poured with cementitious or epoxy binder, ground and polished."},
    {"id": "tile_on_tile", "name": "Existing Tiled Surface (Tile-on-Tile)", "description": "Overlay tiling - new tiles installed directly over existing finished tile."},
    {"id": "rubber_pvc_lino", "name": "Rubber, PVC, Linoleum", "description": "Resilient flexible substrates - require special preparation."},
]

# Tile Types with their standard sizes (from Excel "Tile Type" sheet)
TILE_TYPES = [
    {"id": "vitrified", "name": "Vitrified", "description": "Ceramic tiles with extremely low porosity, fired at high temperatures.",
     "sizes": ["12 x 12 in", "16 x 16 in", "24 x 24 in", "24 x 48 in", "32 x 32 in", "32 x 48 in", "32 x 62 in", "40 x 40 in", "48 x 48 in", "48 x 72 in", "48 x 96 in"]},
    {"id": "ceramic", "name": "Ceramic", "description": "Thin slabs of natural clays, silica, water - hardened by kiln firing.",
     "sizes": ["1 x 1 in", "2 x 2 in", "3 x 6 in", "4 x 4 in", "6 x 6 in", "12 x 12 in", "16 x 16 in", "18 x 18 in", "24 x 24 in"]},
    {"id": "granite", "name": "Granite", "description": "Natural stone tiles cut from granite blocks - quartz, feldspar, mica.",
     "sizes": ["12 x 12 in", "16 x 16 in", "18 x 18 in", "24 x 24 in"]},
    {"id": "stone", "name": "Natural Stone", "description": "Thin slabs of natural rock quarried from earth.",
     "sizes": ["12 x 12 in", "12 x 24 in", "16 x 16 in", "18 x 18 in", "24 x 24 in"]},
    {"id": "marble", "name": "Marble", "description": "Metamorphic rock from limestone - famous for veining.",
     "sizes": ["12 x 12 in", "12 x 24 in", "18 x 18 in", "24 x 24 in", "36 x 36 in"]},
    {"id": "porcelain", "name": "Porcelain", "description": "High-performance ceramic - dense kaolin clay, fired at 1200-1400°C.",
     "sizes": ["6 x 6 in", "12 x 12 in", "12 x 24 in", "18 x 18 in", "24 x 24 in", "24 x 48 in", "32 x 32 in", "48 x 48 in"]},
    {"id": "glass_tile", "name": "Glass", "description": "Glass pieces cut/cast/pressed and kiln-fired. Translucent finish.",
     "sizes": ["1 x 1 in", "2 x 2 in", "3 x 6 in", "4 x 4 in", "6 x 6 in", "12 x 12 in"]},
    {"id": "cement_tile", "name": "Cement Tile (Encaustic)", "description": "Handmade artisanal tiles from cement, sand, marble dust, pigments.",
     "sizes": ["4 x 4 in", "8 x 8 in", "10 x 10 in", "12 x 12 in", "2 x 8 in", "4 x 8 in"]},
    {"id": "mosaic", "name": "Mosaic", "description": "Small tiles assembled in patterns.",
     "sizes": ["1 x 1 in", "2 x 2 in", "1 x 2 in", "12 x 12 in sheets"]},
    {"id": "limestone", "name": "Limestone", "description": "Natural sedimentary stone tiles.",
     "sizes": ["12 x 12 in", "16 x 16 in", "18 x 18 in", "24 x 24 in", "12 x 24 in"]},
    {"id": "quarry", "name": "Quarry", "description": "Unglazed dense ceramic tile from quarried clay.",
     "sizes": ["4 x 4 in", "4 x 8 in", "6 x 6 in", "8 x 8 in", "12 x 12 in"]},
    {"id": "travertine", "name": "Travertine", "description": "Sedimentary natural stone - earthy tones.",
     "sizes": ["4 x 4 in", "6 x 6 in", "12 x 12 in", "16 x 16 in", "18 x 18 in", "24 x 24 in"]},
    {"id": "terracotta", "name": "Terracotta", "description": "Earthen reddish-brown clay tiles, kiln-fired.",
     "sizes": ["4 x 4 in", "6 x 6 in", "8 x 8 in", "12 x 12 in", "16 x 16 in"]},
    {"id": "vinyl", "name": "Vinyl", "description": "Plank/sheet tiles - synthetic flexible.",
     "sizes": ["12 x 12 in", "18 x 18 in", "24 x 24 in", "12 x 24 in", "6 x 36 in", "7 x 48 in", "9 x 48 in"]},
]

# Areas of application
AREAS = ["Kitchen", "Bathroom", "Outdoor / Facade", "Elevation", "Swimming Pool", "Living Room", "Industrial Floor", "Commercial High-Traffic"]

# Substrate -> compatible tile types mapping (based on Excel notes; default = all common types)
COMMON_TILES = ["vitrified", "ceramic", "porcelain", "granite", "marble", "stone"]
ALL_TILES = [t["id"] for t in TILE_TYPES]

SUBSTRATE_TILE_MAP = {
    "concrete": ALL_TILES,
    "cement_plaster": ALL_TILES,
    "cement_screed": ALL_TILES,
    "cement_mortar_beds": ALL_TILES,
    "brick_masonry": ALL_TILES,
    "plywood": ["ceramic", "porcelain", "vitrified", "mosaic", "glass_tile", "vinyl"],
    "gypsum_boards": ["ceramic", "porcelain", "vitrified", "mosaic", "glass_tile"],
    "cement_boards": ALL_TILES,
    "mdf": ["ceramic", "porcelain", "mosaic", "vinyl"],
    "calcium_silicate": ["ceramic", "porcelain", "vitrified", "mosaic", "stone"],
    "metallic": ["ceramic", "porcelain", "mosaic", "glass_tile"],
    "glass": ["mosaic", "glass_tile", "ceramic"],
    "terrazzo": ALL_TILES,
    "tile_on_tile": ["ceramic", "porcelain", "vitrified", "marble", "granite"],
    "rubber_pvc_lino": ["ceramic", "porcelain", "vinyl"],
}

# Kamdhenu Products with full TDS technical parameters
KAMDHENU_PRODUCTS = [
    {
        "code": "K50",
        "name": "K50 Floor & Wall Tile Adhesive",
        "is_type": "Type 1T",
        "en_type": "C1TE",
        "tagline": "Polymer-modified for ceramic and small vitrified tiles in indoor wet/dry zones.",
        "description": "Polymer-modified adhesive for fixing ceramic and vitrified tiles on cementitious substrates. Ideal for indoor wet and dry zones, kitchens, bathrooms, light-traffic floors.",
        "max_tile_size": "Vitrified up to 600x600mm walls/floors, up to 600x1200mm floors",
        "areas": ["Kitchen", "Bathroom", "Living Room"],
        "params": {
            "Open Time": "35-40 minutes",
            "Pot Life": "4-5 hours",
            "Adjustability Time": "~45 minutes",
            "Initial Tensile Adhesion (IS)": "≥ 0.5 N/mm²",
            "Tensile Adhesion after Water Immersion": "0.50-0.60 N/mm²",
            "Tensile Adhesion after Heat Aging": "1.2-1.5 N/mm²",
            "Tensile Adhesion after Freeze-Thaw": "0.55-0.65 N/mm²",
            "Slip Resistance": "≤ 0.5 mm",
            "Shear Adhesion (Dry)": "1.1-1.3 N/mm²",
            "Shear Adhesion (Wet)": "1.0-1.4 N/mm²",
            "Mixing Ratio (powder:water)": "1 : 0.24 by weight",
            "Coverage": "5-6 m² per 20kg @ 3mm bed",
            "Setting Time": "24 hours",
            "Adhesive Thickness": "3-12 mm",
            "Mixed Density": "1.7-1.9 kg/L",
            "Application Temp": "5°C to 35°C",
            "VOC Content": "< 4 g/kg (EPA 24)",
            "Shelf Life": "12 months",
            "Packaging": "20 KG bag",
            "Color": "Grey",
        },
    },
    {
        "code": "K60",
        "name": "K60 Superior Floor & Wall Tile Adhesive",
        "is_type": "Type 2T",
        "en_type": "C2T",
        "tagline": "Versatile polymer-modified adhesive — indoor/outdoor, wet/dry, tile-on-tile.",
        "description": "Highly polymer-modified for ceramic, semi-vitreous, vitrified tiles, and natural stones. Suitable for indoor/outdoor, dry/wet, vertical/horizontal. Recommended for tile-on-tile.",
        "max_tile_size": "Up to 800x800mm",
        "areas": ["Kitchen", "Bathroom", "Living Room", "Outdoor / Facade", "Commercial High-Traffic"],
        "params": {
            "Open Time": "35-40 minutes",
            "Pot Life": "4-5 hours",
            "Adjustability Time": "30-35 minutes",
            "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
            "Tensile Adhesion after Water Immersion": "1.25-1.35 N/mm²",
            "Tensile Adhesion after Heat Aging": "1.15-1.35 N/mm²",
            "Tensile Adhesion after Freeze-Thaw": "1.25-1.35 N/mm²",
            "Slip Resistance": "≤ 0.5 mm",
            "Shear Adhesion (Dry)": "1.50-1.75 N/mm²",
            "Shear Adhesion (Wet)": "1.10-1.35 N/mm²",
            "Mixing Ratio (powder:water)": "Grey 1:0.24-0.26 / White 1:0.25-0.27",
            "Coverage": "5-6 m² per 20kg @ 3mm bed",
            "Setting Time": "24 hours",
            "Adhesive Thickness": "3-12 mm",
            "Mixed Density": "1.65-1.85 kg/L",
            "Application Temp": "5°C to 35°C",
            "VOC Content": "< 1.2 g/kg (EPA 24)",
            "Shelf Life": "12 months",
            "Packaging": "20 KG bag",
            "Color": "Grey, White",
        },
    },
    {
        "code": "K80",
        "name": "K80 Superior Tile & Stone Adhesive",
        "is_type": "Type 2T",
        "en_type": "C2TE",
        "tagline": "High-performance, non-slip — large format vitrified, porcelain, heavy stones.",
        "description": "Polymer-modified with excellent non-slip, engineered for vertical applications. Ideal for large format vitrified, porcelain, heavy natural stones on demanding interior/exterior walls and floors.",
        "max_tile_size": "Up to 1200x1200mm",
        "areas": ["Kitchen", "Bathroom", "Outdoor / Facade", "Elevation", "Living Room", "Commercial High-Traffic"],
        "params": {
            "Open Time": "30 minutes",
            "Pot Life": "4 hours",
            "Adjustability Time": "30 minutes",
            "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
            "Tensile Adhesion after Water Immersion": "1.25-1.35 N/mm²",
            "Tensile Adhesion after Heat Aging": "1.00-1.10 N/mm²",
            "Tensile Adhesion after Freeze-Thaw": "1.25-1.35 N/mm²",
            "Slip Resistance": "0.3-0.4 mm",
            "Shear Adhesion (Dry)": "1.50-1.75 N/mm²",
            "Shear Adhesion (Wet)": "1.10-1.35 N/mm²",
            "Mixing Ratio (powder:water)": "Grey 1:0.27 / White 1:0.29",
            "Coverage": "5-6 m² per 20kg @ 3mm bed",
            "Setting Time": "24 hours",
            "Adhesive Thickness": "3-12 mm",
            "Mixed Density": "1.65 ± 0.05 kg/L",
            "Application Temp": "5°C to 35°C",
            "VOC Content": "< 2 g/kg (EPA 24)",
            "Shelf Life": "12 months",
            "Packaging": "20 KG bag",
            "Color": "Grey, White",
        },
    },
    {
        "code": "K90",
        "name": "K90 Paramount Tile & Stone Adhesive",
        "is_type": "Type 3TS1",
        "en_type": "C2TES1",
        "tagline": "Highly flexible, deformable — challenging substrates like plywood, gypsum, facades.",
        "description": "Highly flexible polymer-modified with superior non-slip and high deformability. Engineered for challenging substrates — plywood, gypsum boards, facades. Suitable for all interior/exterior dry/wet areas including pools.",
        "max_tile_size": "Up to 1200x2400mm",
        "areas": ["Kitchen", "Bathroom", "Outdoor / Facade", "Elevation", "Swimming Pool", "Commercial High-Traffic"],
        "params": {
            "Open Time": "30-35 minutes",
            "Pot Life": "4-5 hours",
            "Adjustability Time": "30-35 minutes",
            "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
            "Tensile Adhesion after Water Immersion": "1.25-1.75 N/mm²",
            "Tensile Adhesion after Heat Aging": "1.25-1.50 N/mm²",
            "Tensile Adhesion after Freeze-Thaw": "1.50-2.00 N/mm²",
            "Slip Resistance": "0.20-0.30 mm",
            "Shear Adhesion (Dry)": "1.75-2.00 N/mm²",
            "Shear Adhesion (Wet)": "1.30-1.55 N/mm²",
            "Transverse Deformation (S1)": "2.70-2.80 mm",
            "Mixing Ratio (powder:water)": "Grey 1:0.24-0.26 / White 1:0.25-0.27",
            "Coverage": "5-6 m² per 20kg @ 3mm bed",
            "Setting Time": "24 hours",
            "Adhesive Thickness": "3-12 mm",
            "Mixed Density": "1.65-1.85 kg/L",
            "Application Temp": "5°C to 35°C",
            "VOC Content": "< 1.2 g/kg (EPA 24)",
            "Shelf Life": "12 months",
            "Packaging": "20 KG bag",
            "Color": "Grey, White",
        },
    },
    {
        "code": "KX",
        "name": "Kamdhenu X — The Ultimate Adhesive",
        "is_type": "Type 4TS2",
        "en_type": "C2TES2",
        "tagline": "Highly deformable, extended open time — extra-large slabs, facades, industrial.",
        "description": "Advanced highly deformable polymer-modified adhesive with extended open time and superior non-slip. For all heavy and extra-large format tiles/slabs on facades, industrial floors, areas with extreme thermal variation or vibration.",
        "max_tile_size": "Extra-large slabs, no upper limit",
        "areas": ["Kitchen", "Bathroom", "Outdoor / Facade", "Elevation", "Swimming Pool", "Industrial Floor", "Commercial High-Traffic"],
        "params": {
            "Open Time": "Min. 40 minutes",
            "Pot Life": "4-4.5 hours",
            "Adjustability Time": "~40 minutes",
            "Initial Tensile Adhesion (IS)": "≥ 1.5 N/mm²",
            "Tensile Adhesion after Water Immersion": "1.25-1.35 N/mm²",
            "Tensile Adhesion after Heat Aging": "≥ 1.5 N/mm²",
            "Tensile Adhesion after Freeze-Thaw": "1.25-1.35 N/mm²",
            "Slip Resistance": "0.3-0.4 mm",
            "Shear Adhesion (Dry)": "≥ 1.5 N/mm²",
            "Shear Adhesion (Wet)": "≥ 1.0 N/mm²",
            "Deformability (S2)": "≥ 3.5 mm",
            "Mixing Ratio (powder:water)": "Grey 100:28 / White 100:30",
            "Coverage": "5-6 m² per 20kg @ 3mm bed",
            "Setting Time": "24 hours",
            "Adhesive Thickness": "3-12 mm",
            "Mixed Density": "1.6-1.7 kg/L",
            "Application Temp": "5°C to 35°C",
            "VOC Content": "< 0.2 g/L",
            "Shelf Life": "12 months",
            "Packaging": "20 KG bag",
            "Color": "White",
        },
    },
]


# Recommendation logic - by tile type, max tile size, area
def recommend_kamdhenu(substrate_id, tile_type_id, tile_size, area):
    """Returns best Kamdhenu product code for given selection."""
    # extract longest dimension from tile_size like "24 x 48 in"
    import re
    nums = re.findall(r"\d+", tile_size or "")
    longest_in = max(int(n) for n in nums) if nums else 12
    longest_mm = longest_in * 25.4

    # Special substrates need flexible adhesive
    if substrate_id in ("plywood", "gypsum_boards", "mdf", "metallic", "glass", "rubber_pvc_lino", "tile_on_tile"):
        if longest_mm >= 1000:
            return "KX"
        return "K90"

    # Outdoor / pool / industrial -> KX or K90
    if area in ("Swimming Pool", "Industrial Floor"):
        return "KX"
    if area in ("Outdoor / Facade", "Elevation"):
        if longest_mm >= 800:
            return "KX"
        return "K90"

    # By tile type
    if tile_type_id in ("marble", "granite", "stone", "limestone", "travertine"):
        if longest_mm >= 1000:
            return "K90"
        return "K80"

    if tile_type_id == "porcelain" or tile_type_id == "vitrified":
        if longest_mm >= 1200:
            return "KX"
        if longest_mm >= 800:
            return "K90"
        if longest_mm >= 600:
            return "K80"
        return "K60"

    if tile_type_id in ("ceramic", "mosaic", "glass_tile", "cement_tile", "terracotta", "quarry", "vinyl"):
        if longest_mm >= 600:
            return "K80"
        return "K50"

    return "K60"


# Competitor Brands & Products with Type mapping
COMPETITORS = [
    {
        "id": "myk_laticrete",
        "name": "MYK Laticrete",
        "products": [
            {"name": "LATICRETE 303 Floor & Wall Tile Adhesive", "is_type": "Type 1T", "en_type": "C1T", "competes_with": "K50"},
            {"name": "LATICRETE 307", "is_type": "Type 2T", "en_type": "C1T", "competes_with": "K60"},
            {"name": "LATICRETE 320 Stone Adhesive", "is_type": "Type 2", "en_type": "C2TE", "competes_with": "K60"},
            {"name": "LATICRETE 313", "is_type": "Type 2T", "en_type": "C1TE", "competes_with": "K60"},
            {"name": "LATICRETE 325 Shear Wall Adhesive", "is_type": "Type 2T", "en_type": "C2T", "competes_with": "K80"},
            {"name": "LATICRETE 315 Plus", "is_type": "Type 2T", "en_type": "C2TE", "competes_with": "K80"},
            {"name": "LATICRETE 335 Super Flex", "is_type": "Type 3TS1", "en_type": "C2TES2", "competes_with": "K90"},
            {"name": "LATICRETE 325 High Flex", "is_type": "Type 3T", "en_type": "C2TE", "competes_with": "K90"},
            {"name": "LATICRETE 345 Super Flex", "is_type": "Type 4TS2", "en_type": "C2ETS2", "competes_with": "KX"},
            {"name": "LATICRETE 335 Maxi", "is_type": "Type 4TS1", "en_type": "C2TES1", "competes_with": "KX"},
            {"name": "DWA 215", "is_type": "Type 4TS2", "en_type": "D2TES2", "competes_with": "KX"},
        ],
    },
    {
        "id": "roff",
        "name": "Roff (Pidilite)",
        "products": [
            {"name": "Roff New Construction Adhesive (NCA)", "is_type": "Type 1T", "en_type": "C1T", "competes_with": "K50"},
            {"name": "Roff Tile Bonder", "is_type": "Type 1", "en_type": "C1", "competes_with": "K50"},
            {"name": "Roff Non-Skid Adhesive (NSA)", "is_type": "Type 2T", "en_type": "C2T", "competes_with": "K60"},
            {"name": "Roff Vitrofix Adhesive", "is_type": "Type 2T", "en_type": "C2T", "competes_with": "K60"},
            {"name": "Roff Vitrofix Ultra Adhesive", "is_type": "Type 3T", "en_type": "C2TE", "competes_with": "K80"},
            {"name": "Roff Extrofix Adhesive", "is_type": "Type 3TS1", "en_type": "C2TES1", "competes_with": "K90"},
            {"name": "Roff Extrofix Ultra Adhesive", "is_type": "Type 4TS1", "en_type": "C2TES1 S1", "competes_with": "K90"},
            {"name": "Roff Yogafix Adhesive", "is_type": "Type 4TS2", "en_type": "C2TES2", "competes_with": "KX"},
            {"name": "Roff Master Fix Adhesive", "is_type": "Type 5 S2", "en_type": "R2T", "competes_with": "KX"},
            {"name": "Roff Vertifix", "is_type": "Type 5 S2", "en_type": "R2T", "competes_with": "KX"},
        ],
    },
    {
        "id": "mapei",
        "name": "Mapei",
        "products": [
            {"name": "KERABOND T", "is_type": "Type 1T", "en_type": "C1T", "competes_with": "K50"},
            {"name": "MAPESET IN", "is_type": "Type 2", "en_type": "C1", "competes_with": "K50"},
            {"name": "KERASET T", "is_type": "Type 2T", "en_type": "C2T", "competes_with": "K60"},
            {"name": "ADESILEX P10", "is_type": "Type 3T", "en_type": "C2TE", "competes_with": "K80"},
            {"name": "ADESILEX P9", "is_type": "Type 3T", "en_type": "C2TE", "competes_with": "K80"},
            {"name": "KERAFLEX", "is_type": "Type 3T", "en_type": "C2TE", "competes_with": "K80"},
            {"name": "KERABOND PLUS", "is_type": "Type 3", "en_type": "C2E", "competes_with": "K80"},
            {"name": "KERAFLEX EASY S1 ZERO", "is_type": "Type 4S1", "en_type": "C2ES1", "competes_with": "K90"},
            {"name": "KERAFLEX MAXI S1 ZERO", "is_type": "Type 4TS1", "en_type": "C2TES1", "competes_with": "K90"},
            {"name": "ULTRALITE S1", "is_type": "Type 4TS1", "en_type": "C2TES1", "competes_with": "K90"},
            {"name": "ULTRALITE S2", "is_type": "Type 4TS2", "en_type": "C2TES2", "competes_with": "KX"},
            {"name": "ELASTORAPID", "is_type": "Type 4TS2", "en_type": "C2FTS2", "competes_with": "KX"},
            {"name": "GRANIRAPID", "is_type": "Type 4TS1", "en_type": "C2FTS1", "competes_with": "KX"},
        ],
    },
    {
        "id": "kerakoll",
        "name": "Kerakoll",
        "products": [
            {"name": "Biotile", "is_type": "Type 1T", "en_type": "C1T", "competes_with": "K50"},
            {"name": "Bioflex", "is_type": "Type 3T", "en_type": "C2TE", "competes_with": "K80"},
            {"name": "Bioflex S1", "is_type": "Type 4TS1", "en_type": "C2TES1", "competes_with": "K90"},
            {"name": "H40 Gel", "is_type": "Type 4TS1", "en_type": "C2TES1", "competes_with": "K90"},
            {"name": "Superflex", "is_type": "Type 5TS2", "en_type": "C2TES2", "competes_with": "KX"},
        ],
    },

]

DEFAULT_TDS_UPDATE_FREQUENCY_DAYS = 15


def _with_tds_defaults(product):
    """Attach TDS sync metadata defaults to competitor products."""
    seeded = dict(product)
    seeded.setdefault("tds_url", "")
    seeded.setdefault("tds_file_hash", "")
    seeded.setdefault("tds_text_hash", "")
    seeded.setdefault("last_checked_at", None)
    seeded.setdefault("last_updated_at", None)
    seeded.setdefault("next_check_at", None)
    seeded.setdefault("update_frequency_days", DEFAULT_TDS_UPDATE_FREQUENCY_DAYS)
    seeded.setdefault("report_status", "due")
    seeded.setdefault("technical_report", None)
    seeded.setdefault("pending_technical_report", None)
    seeded.setdefault("tds_source_version", "seed-v1")
    return seeded


COMPETITORS = [
    {
        **competitor,
        "products": [_with_tds_defaults(product) for product in competitor["products"]],
    }
    for competitor in COMPETITORS
]


# Estimated competitor product technical params (industry-standard ranges per type)
TYPE_DEFAULTS = {
    "C1T": {
        "Open Time": "20-30 minutes",
        "Pot Life": "2-3 hours",
        "Adjustability Time": "10-15 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 0.5 N/mm²",
        "Tensile Adhesion after Water Immersion": "0.45-0.55 N/mm²",
        "Tensile Adhesion after Heat Aging": "0.50-0.60 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "0.50-0.55 N/mm²",
        "Slip Resistance": "≤ 0.5 mm",
        "Shear Adhesion (Dry)": "1.0-1.2 N/mm²",
        "Shear Adhesion (Wet)": "0.9-1.1 N/mm²",
        "Mixing Ratio (powder:water)": "1 : 0.25",
        "Coverage": "4-5 m² per 20kg @ 3mm bed",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "3-10 mm",
        "Mixed Density": "1.6-1.8 kg/L",
        "Application Temp": "5°C to 35°C",
        "VOC Content": "< 5 g/kg",
        "Shelf Life": "9-12 months",
        "Packaging": "20 KG bag",
        "Color": "Grey",
    },
    "C1TE": {
        "Open Time": "30 minutes",
        "Pot Life": "3-4 hours",
        "Adjustability Time": "20-30 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 0.5 N/mm²",
        "Tensile Adhesion after Water Immersion": "0.50-0.60 N/mm²",
        "Tensile Adhesion after Heat Aging": "0.55-0.65 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "0.55-0.65 N/mm²",
        "Slip Resistance": "≤ 0.5 mm",
        "Shear Adhesion (Dry)": "1.1-1.3 N/mm²",
        "Shear Adhesion (Wet)": "1.0-1.2 N/mm²",
        "Mixing Ratio (powder:water)": "1 : 0.24-0.26",
        "Coverage": "4-5 m² per 20kg @ 3mm bed",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "3-10 mm",
        "Mixed Density": "1.6-1.8 kg/L",
        "Application Temp": "5°C to 35°C",
        "VOC Content": "< 4 g/kg",
        "Shelf Life": "12 months",
        "Packaging": "20 KG bag",
        "Color": "Grey",
    },
    "C2T": {
        "Open Time": "30 minutes",
        "Pot Life": "3-4 hours",
        "Adjustability Time": "20-30 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
        "Tensile Adhesion after Water Immersion": "1.0-1.1 N/mm²",
        "Tensile Adhesion after Heat Aging": "1.0-1.1 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "1.0-1.1 N/mm²",
        "Slip Resistance": "≤ 0.5 mm",
        "Shear Adhesion (Dry)": "1.3-1.5 N/mm²",
        "Shear Adhesion (Wet)": "1.0-1.2 N/mm²",
        "Mixing Ratio (powder:water)": "1 : 0.25",
        "Coverage": "4-5 m² per 20kg @ 3mm bed",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "3-12 mm",
        "Mixed Density": "1.6-1.8 kg/L",
        "Application Temp": "5°C to 35°C",
        "VOC Content": "< 3 g/kg",
        "Shelf Life": "12 months",
        "Packaging": "20 KG bag",
        "Color": "Grey, White",
    },
    "C2TE": {
        "Open Time": "30 minutes",
        "Pot Life": "3-4 hours",
        "Adjustability Time": "30 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
        "Tensile Adhesion after Water Immersion": "1.10-1.25 N/mm²",
        "Tensile Adhesion after Heat Aging": "1.00-1.10 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "1.10-1.25 N/mm²",
        "Slip Resistance": "≤ 0.5 mm",
        "Shear Adhesion (Dry)": "1.4-1.6 N/mm²",
        "Shear Adhesion (Wet)": "1.0-1.2 N/mm²",
        "Mixing Ratio (powder:water)": "1 : 0.25-0.27",
        "Coverage": "4-5 m² per 20kg @ 3mm bed",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "3-12 mm",
        "Mixed Density": "1.6-1.8 kg/L",
        "Application Temp": "5°C to 35°C",
        "VOC Content": "< 2 g/kg",
        "Shelf Life": "12 months",
        "Packaging": "20 KG bag",
        "Color": "Grey, White",
    },
    "C2TES1": {
        "Open Time": "30 minutes",
        "Pot Life": "3-4 hours",
        "Adjustability Time": "30 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
        "Tensile Adhesion after Water Immersion": "1.20-1.50 N/mm²",
        "Tensile Adhesion after Heat Aging": "1.10-1.30 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "1.30-1.60 N/mm²",
        "Slip Resistance": "0.3-0.4 mm",
        "Shear Adhesion (Dry)": "1.6-1.8 N/mm²",
        "Shear Adhesion (Wet)": "1.2-1.4 N/mm²",
        "Transverse Deformation (S1)": "2.5-2.7 mm",
        "Mixing Ratio (powder:water)": "1 : 0.25-0.28",
        "Coverage": "4-5 m² per 20kg @ 3mm bed",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "3-12 mm",
        "Mixed Density": "1.6-1.8 kg/L",
        "Application Temp": "5°C to 35°C",
        "VOC Content": "< 2 g/kg",
        "Shelf Life": "12 months",
        "Packaging": "20 KG bag",
        "Color": "Grey, White",
    },
    "C2TES2": {
        "Open Time": "30-40 minutes",
        "Pot Life": "3-4 hours",
        "Adjustability Time": "30-35 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 1.0 N/mm²",
        "Tensile Adhesion after Water Immersion": "1.20-1.30 N/mm²",
        "Tensile Adhesion after Heat Aging": "1.00-1.10 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "1.20-1.30 N/mm²",
        "Slip Resistance": "0.3-0.4 mm",
        "Shear Adhesion (Dry)": "1.5-1.7 N/mm²",
        "Shear Adhesion (Wet)": "1.2-1.4 N/mm²",
        "Deformability (S2)": "≥ 3.0 mm",
        "Mixing Ratio (powder:water)": "1 : 0.27-0.30",
        "Coverage": "4-5 m² per 20kg @ 3mm bed",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "3-12 mm",
        "Mixed Density": "1.6-1.7 kg/L",
        "Application Temp": "5°C to 35°C",
        "VOC Content": "< 1 g/kg",
        "Shelf Life": "12 months",
        "Packaging": "20 KG bag",
        "Color": "White",
    },
    "R2T": {
        "Open Time": "40-60 minutes",
        "Pot Life": "30-45 minutes",
        "Adjustability Time": "30 minutes",
        "Initial Tensile Adhesion (IS)": "≥ 2.0 N/mm² (Reactive)",
        "Tensile Adhesion after Water Immersion": "≥ 2.0 N/mm²",
        "Tensile Adhesion after Heat Aging": "≥ 2.0 N/mm²",
        "Tensile Adhesion after Freeze-Thaw": "≥ 2.0 N/mm²",
        "Slip Resistance": "0.2-0.3 mm",
        "Shear Adhesion (Dry)": "≥ 2.0 N/mm²",
        "Shear Adhesion (Wet)": "≥ 2.0 N/mm²",
        "Mixing Ratio (powder:water)": "Two-component (epoxy/PU)",
        "Coverage": "3-4 m² per 5kg",
        "Setting Time": "24 hours",
        "Adhesive Thickness": "1-10 mm",
        "Mixed Density": "1.5-1.7 kg/L",
        "Application Temp": "10°C to 30°C",
        "VOC Content": "< 1 g/kg",
        "Shelf Life": "12 months",
        "Packaging": "5 KG kit",
        "Color": "Grey, White",
    },
}

# Build helper to enrich competitor products with default params
def enrich_competitor_params(product):
    """Returns dict of params for a competitor product based on EN type."""
    technical_report = product.get("technical_report")
    if isinstance(technical_report, dict) and technical_report:
        return technical_report.copy()

    en = (product.get("en_type") or "").upper().replace(" ", "")
    # Match base type
    for key in ["C2TES2", "C2TES1", "C2TE", "C2T", "C1TE", "C1T", "R2T"]:
        if key in en:
            return TYPE_DEFAULTS[key].copy()
    return TYPE_DEFAULTS["C2TE"].copy()
