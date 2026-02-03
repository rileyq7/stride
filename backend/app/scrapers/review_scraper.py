"""
Review site scraper for shoe specifications.

This scraper contains a comprehensive catalog of running shoe specifications
gathered from review sites like Doctors of Running, Believe in the Run, and
Running Warehouse.
"""

import re
import logging
import httpx
from typing import Optional, List, Dict, Any
from decimal import Decimal
from dataclasses import dataclass
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus

logger = logging.getLogger(__name__)


@dataclass
class ShoeSpecs:
    """Scraped shoe specifications."""
    brand: str
    name: str
    msrp: Optional[Decimal] = None
    weight_oz: Optional[Decimal] = None
    drop_mm: Optional[Decimal] = None
    stack_height_heel_mm: Optional[Decimal] = None
    stack_height_forefoot_mm: Optional[Decimal] = None
    cushion_type: Optional[str] = None
    cushion_level: Optional[str] = None
    terrain: str = 'road'
    subcategory: Optional[str] = None
    has_carbon_plate: bool = False
    has_rocker: bool = False
    primary_image_url: Optional[str] = None
    source_url: Optional[str] = None


class ReviewSiteScraper:
    """Scraper for running shoe review sites."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    # Comprehensive shoe catalog
    SHOE_CATALOG = {
        'hoka': {
            # Neutral Road
            'clifton 10': {'name': 'Clifton 10', 'msrp': 150, 'weight_oz': 9.2, 'drop_mm': 5, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 27, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'clifton 9': {'name': 'Clifton 9', 'msrp': 145, 'weight_oz': 9.3, 'drop_mm': 5, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 27, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'bondi 8': {'name': 'Bondi 8', 'msrp': 165, 'weight_oz': 10.8, 'drop_mm': 4, 'stack_height_heel_mm': 36, 'stack_height_forefoot_mm': 32, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'bondi 9': {'name': 'Bondi 9', 'msrp': 175, 'weight_oz': 10.7, 'drop_mm': 4, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 33, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'mach 6': {'name': 'Mach 6', 'msrp': 140, 'weight_oz': 7.8, 'drop_mm': 5, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 29, 'cushion_type': 'PEBA', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'mach 5': {'name': 'Mach 5', 'msrp': 140, 'weight_oz': 7.7, 'drop_mm': 5, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Profly', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'rincon 4': {'name': 'Rincon 4', 'msrp': 115, 'weight_oz': 7.2, 'drop_mm': 5, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'rincon 3': {'name': 'Rincon 3', 'msrp': 115, 'weight_oz': 7.3, 'drop_mm': 5, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'kawana 2': {'name': 'Kawana 2', 'msrp': 145, 'weight_oz': 9.5, 'drop_mm': 5, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            # Stability Road
            'arahi 7': {'name': 'Arahi 7', 'msrp': 140, 'weight_oz': 9.7, 'drop_mm': 5, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability', 'has_rocker': True},
            'arahi 6': {'name': 'Arahi 6', 'msrp': 140, 'weight_oz': 9.6, 'drop_mm': 5, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability', 'has_rocker': True},
            'gaviota 5': {'name': 'Gaviota 5', 'msrp': 170, 'weight_oz': 10.8, 'drop_mm': 5, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 30, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability', 'has_rocker': True},
            # Racing
            'mach x': {'name': 'Mach X', 'msrp': 180, 'weight_oz': 8.7, 'drop_mm': 5, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 32, 'cushion_type': 'PEBA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'rocket x 2': {'name': 'Rocket X 2', 'msrp': 250, 'weight_oz': 7.7, 'drop_mm': 5, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 34, 'cushion_type': 'PEBA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'cielo x1': {'name': 'Cielo X1', 'msrp': 275, 'weight_oz': 6.7, 'drop_mm': 5, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 34, 'cushion_type': 'PEBA', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            # Trail
            'speedgoat 6': {'name': 'Speedgoat 6', 'msrp': 165, 'weight_oz': 10.2, 'drop_mm': 4, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral', 'has_rocker': True},
            'speedgoat 5': {'name': 'Speedgoat 5', 'msrp': 155, 'weight_oz': 10.4, 'drop_mm': 4, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral', 'has_rocker': True},
            'challenger atr 7': {'name': 'Challenger ATR 7', 'msrp': 145, 'weight_oz': 9.4, 'drop_mm': 5, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral', 'has_rocker': True},
            'torrent 3': {'name': 'Torrent 3', 'msrp': 130, 'weight_oz': 8.5, 'drop_mm': 5, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 25, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral', 'has_rocker': True},
            'zinal 2': {'name': 'Zinal 2', 'msrp': 170, 'weight_oz': 9.0, 'drop_mm': 5, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 26, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral', 'has_rocker': True},
            'tecton x 2': {'name': 'Tecton X 2', 'msrp': 225, 'weight_oz': 9.5, 'drop_mm': 5, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 28, 'cushion_type': 'PEBA', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'stinson atr 7': {'name': 'Stinson ATR 7', 'msrp': 170, 'weight_oz': 11.6, 'drop_mm': 4, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 35, 'cushion_type': 'Compression-Molded EVA', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral', 'has_rocker': True},
        },
        'brooks': {
            # Neutral Road
            'ghost 16': {'name': 'Ghost 16', 'msrp': 140, 'weight_oz': 9.8, 'drop_mm': 12, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 23, 'cushion_type': 'DNA LOFT v2', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'ghost 15': {'name': 'Ghost 15', 'msrp': 140, 'weight_oz': 9.6, 'drop_mm': 12, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 23, 'cushion_type': 'DNA LOFT', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'glycerin 21': {'name': 'Glycerin 21', 'msrp': 160, 'weight_oz': 10.1, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'glycerin 20': {'name': 'Glycerin 20', 'msrp': 160, 'weight_oz': 10.2, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'glycerin stealthfit 21': {'name': 'Glycerin StealthFit 21', 'msrp': 170, 'weight_oz': 9.9, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'launch 10': {'name': 'Launch 10', 'msrp': 110, 'weight_oz': 8.1, 'drop_mm': 10, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 18, 'cushion_type': 'DNA', 'cushion_level': 'light', 'terrain': 'road', 'subcategory': 'neutral'},
            'revel 6': {'name': 'Revel 6', 'msrp': 100, 'weight_oz': 9.2, 'drop_mm': 8, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 20, 'cushion_type': 'BioMoGo DNA', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'trace 3': {'name': 'Trace 3', 'msrp': 100, 'weight_oz': 9.6, 'drop_mm': 8, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 22, 'cushion_type': 'BioMoGo DNA', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            # Stability Road
            'adrenaline gts 24': {'name': 'Adrenaline GTS 24', 'msrp': 140, 'weight_oz': 10.2, 'drop_mm': 12, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 21, 'cushion_type': 'DNA LOFT', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'adrenaline gts 23': {'name': 'Adrenaline GTS 23', 'msrp': 140, 'weight_oz': 10.0, 'drop_mm': 12, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 21, 'cushion_type': 'DNA LOFT', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'glycerin gts 21': {'name': 'Glycerin GTS 21', 'msrp': 170, 'weight_oz': 10.6, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            'addiction gts 16': {'name': 'Addiction GTS 16', 'msrp': 150, 'weight_oz': 11.2, 'drop_mm': 12, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 21, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            'transcend 7': {'name': 'Transcend 7', 'msrp': 170, 'weight_oz': 11.0, 'drop_mm': 10, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 25, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'hyperion max': {'name': 'Hyperion Max', 'msrp': 180, 'weight_oz': 8.1, 'drop_mm': 8, 'stack_height_heel_mm': 36, 'stack_height_forefoot_mm': 28, 'cushion_type': 'DNA FLASH', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'racing', 'has_rocker': True},
            'hyperion tempo': {'name': 'Hyperion Tempo', 'msrp': 150, 'weight_oz': 7.5, 'drop_mm': 8, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 24, 'cushion_type': 'DNA FLASH', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'racing'},
            'hyperion elite 4': {'name': 'Hyperion Elite 4', 'msrp': 250, 'weight_oz': 6.8, 'drop_mm': 8, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 31, 'cushion_type': 'DNA FLASH', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'hyperion gts': {'name': 'Hyperion GTS', 'msrp': 180, 'weight_oz': 8.4, 'drop_mm': 8, 'stack_height_heel_mm': 36, 'stack_height_forefoot_mm': 28, 'cushion_type': 'DNA FLASH', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability', 'has_rocker': True},
            # Trail
            'cascadia 18': {'name': 'Cascadia 18', 'msrp': 150, 'weight_oz': 10.6, 'drop_mm': 8, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 24, 'cushion_type': 'DNA LOFT', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'cascadia 17': {'name': 'Cascadia 17', 'msrp': 150, 'weight_oz': 10.4, 'drop_mm': 8, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 24, 'cushion_type': 'DNA LOFT', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'caldera 7': {'name': 'Caldera 7', 'msrp': 170, 'weight_oz': 11.2, 'drop_mm': 4, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 31, 'cushion_type': 'DNA LOFT', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'catamount 3': {'name': 'Catamount 3', 'msrp': 180, 'weight_oz': 8.4, 'drop_mm': 6, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 22, 'cushion_type': 'DNA FLASH', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'racing'},
            'divide 5': {'name': 'Divide 5', 'msrp': 100, 'weight_oz': 10.2, 'drop_mm': 8, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 22, 'cushion_type': 'BioMoGo DNA', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
        'asics': {
            # Neutral Road
            'gel-nimbus 26': {'name': 'Gel-Nimbus 26', 'msrp': 160, 'weight_oz': 10.6, 'drop_mm': 8, 'stack_height_heel_mm': 41, 'stack_height_forefoot_mm': 33, 'cushion_type': 'FF BLAST PLUS ECO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'gel-nimbus 25': {'name': 'Gel-Nimbus 25', 'msrp': 160, 'weight_oz': 10.2, 'drop_mm': 8, 'stack_height_heel_mm': 41, 'stack_height_forefoot_mm': 33, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'novablast 4': {'name': 'Novablast 4', 'msrp': 140, 'weight_oz': 9.5, 'drop_mm': 8, 'stack_height_heel_mm': 41, 'stack_height_forefoot_mm': 33, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'novablast 3': {'name': 'Novablast 3', 'msrp': 140, 'weight_oz': 9.3, 'drop_mm': 8, 'stack_height_heel_mm': 41, 'stack_height_forefoot_mm': 33, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'gel-cumulus 26': {'name': 'Gel-Cumulus 26', 'msrp': 130, 'weight_oz': 9.9, 'drop_mm': 8, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 30, 'cushion_type': 'FF BLAST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'gel-cumulus 25': {'name': 'Gel-Cumulus 25', 'msrp': 130, 'weight_oz': 9.7, 'drop_mm': 8, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 30, 'cushion_type': 'FF BLAST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'superblast': {'name': 'Superblast', 'msrp': 200, 'weight_oz': 9.2, 'drop_mm': 8, 'stack_height_heel_mm': 47, 'stack_height_forefoot_mm': 39, 'cushion_type': 'FF TURBO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'dynablast 4': {'name': 'Dynablast 4', 'msrp': 100, 'weight_oz': 8.5, 'drop_mm': 10, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 22, 'cushion_type': 'FF BLAST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'magic speed 3': {'name': 'Magic Speed 3', 'msrp': 170, 'weight_oz': 7.7, 'drop_mm': 8, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 31, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            # Stability Road
            'gel-kayano 31': {'name': 'Gel-Kayano 31', 'msrp': 180, 'weight_oz': 11.0, 'drop_mm': 10, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 30, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            'gel-kayano 30': {'name': 'Gel-Kayano 30', 'msrp': 180, 'weight_oz': 10.9, 'drop_mm': 10, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 30, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            'gt-2000 13': {'name': 'GT-2000 13', 'msrp': 140, 'weight_oz': 10.2, 'drop_mm': 8, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 29, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'gt-2000 12': {'name': 'GT-2000 12', 'msrp': 140, 'weight_oz': 10.0, 'drop_mm': 8, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 29, 'cushion_type': 'FF BLAST PLUS', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'gt-1000 13': {'name': 'GT-1000 13', 'msrp': 100, 'weight_oz': 9.5, 'drop_mm': 8, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 24, 'cushion_type': 'FF BLAST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'metaspeed sky paris': {'name': 'Metaspeed Sky Paris', 'msrp': 275, 'weight_oz': 6.5, 'drop_mm': 5, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 34, 'cushion_type': 'FF TURBO PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'metaspeed edge paris': {'name': 'Metaspeed Edge Paris', 'msrp': 275, 'weight_oz': 6.9, 'drop_mm': 8, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 29, 'cushion_type': 'FF TURBO PLUS', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            # Trail
            'gel-trabuco 12': {'name': 'Gel-Trabuco 12', 'msrp': 140, 'weight_oz': 11.5, 'drop_mm': 8, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 26, 'cushion_type': 'FF BLAST', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'gel-venture 9': {'name': 'Gel-Venture 9', 'msrp': 75, 'weight_oz': 10.4, 'drop_mm': 10, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 18, 'cushion_type': 'AMPLIFOAM', 'cushion_level': 'light', 'terrain': 'trail', 'subcategory': 'neutral'},
            'fujispeed 3': {'name': 'Fuji Speed 3', 'msrp': 190, 'weight_oz': 8.8, 'drop_mm': 4, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 30, 'cushion_type': 'FF BLAST', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'racing', 'has_carbon_plate': True},
        },
        'nike': {
            # Neutral Road
            'pegasus 41': {'name': 'Pegasus 41', 'msrp': 140, 'weight_oz': 10.6, 'drop_mm': 10, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 23, 'cushion_type': 'React X', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'pegasus 40': {'name': 'Pegasus 40', 'msrp': 135, 'weight_oz': 10.4, 'drop_mm': 10, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 23, 'cushion_type': 'React', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'vomero 18': {'name': 'Vomero 18', 'msrp': 160, 'weight_oz': 10.9, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'vomero 17': {'name': 'Vomero 17', 'msrp': 160, 'weight_oz': 10.8, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'invincible 3': {'name': 'Invincible 3', 'msrp': 180, 'weight_oz': 10.9, 'drop_mm': 9, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 28, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'infinity run 4': {'name': 'InfinityRN 4', 'msrp': 160, 'weight_oz': 10.6, 'drop_mm': 9, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 28, 'cushion_type': 'React X', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'zoomx streakfly': {'name': 'ZoomX Streakfly', 'msrp': 170, 'weight_oz': 6.6, 'drop_mm': 6, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 24, 'cushion_type': 'ZoomX', 'cushion_level': 'light', 'terrain': 'road', 'subcategory': 'racing'},
            # Stability Road
            'structure 25': {'name': 'Structure 25', 'msrp': 140, 'weight_oz': 10.5, 'drop_mm': 10, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 25, 'cushion_type': 'React X', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'structure 24': {'name': 'Structure 24', 'msrp': 140, 'weight_oz': 10.3, 'drop_mm': 10, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 25, 'cushion_type': 'React', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'vaporfly 3': {'name': 'Vaporfly 3', 'msrp': 260, 'weight_oz': 6.6, 'drop_mm': 8, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 32, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'alphafly 3': {'name': 'Alphafly 3', 'msrp': 285, 'weight_oz': 7.4, 'drop_mm': 4, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 36, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'alphafly 2': {'name': 'Alphafly 2', 'msrp': 275, 'weight_oz': 7.1, 'drop_mm': 4, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 36, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'zoom fly 5': {'name': 'Zoom Fly 5', 'msrp': 170, 'weight_oz': 9.1, 'drop_mm': 8, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 31, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            # Trail
            'pegasus trail 5': {'name': 'Pegasus Trail 5', 'msrp': 150, 'weight_oz': 10.8, 'drop_mm': 10, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 23, 'cushion_type': 'React', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'pegasus trail 4': {'name': 'Pegasus Trail 4', 'msrp': 150, 'weight_oz': 10.6, 'drop_mm': 10, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 23, 'cushion_type': 'React', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'wildhorse 8': {'name': 'Wildhorse 8', 'msrp': 140, 'weight_oz': 10.4, 'drop_mm': 8, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 22, 'cushion_type': 'React', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'zegama 2': {'name': 'Zegama 2', 'msrp': 180, 'weight_oz': 9.5, 'drop_mm': 4, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 31, 'cushion_type': 'ZoomX', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'racing', 'has_carbon_plate': True},
            'ultrafly trail': {'name': 'Ultrafly Trail', 'msrp': 170, 'weight_oz': 10.2, 'drop_mm': 8, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 29, 'cushion_type': 'ZoomX', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
        'saucony': {
            # Neutral Road
            'ride 17': {'name': 'Ride 17', 'msrp': 140, 'weight_oz': 9.3, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'PWRRUN+', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'ride 16': {'name': 'Ride 16', 'msrp': 140, 'weight_oz': 9.2, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'PWRRUN', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'triumph 22': {'name': 'Triumph 22', 'msrp': 160, 'weight_oz': 10.2, 'drop_mm': 10, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 29, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'triumph 21': {'name': 'Triumph 21', 'msrp': 160, 'weight_oz': 10.0, 'drop_mm': 10, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 29, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'kinvara 15': {'name': 'Kinvara 15', 'msrp': 130, 'weight_oz': 7.5, 'drop_mm': 4, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 25, 'cushion_type': 'PWRRUN+', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'kinvara 14': {'name': 'Kinvara 14', 'msrp': 130, 'weight_oz': 7.3, 'drop_mm': 4, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 25, 'cushion_type': 'PWRRUN+', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'freedom 6': {'name': 'Freedom 6', 'msrp': 150, 'weight_oz': 7.8, 'drop_mm': 4, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 27, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'tempus': {'name': 'Tempus', 'msrp': 160, 'weight_oz': 10.2, 'drop_mm': 8, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 29, 'cushion_type': 'PWRRUN+', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            # Stability Road
            'guide 17': {'name': 'Guide 17', 'msrp': 140, 'weight_oz': 9.5, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'PWRRUN+', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'guide 16': {'name': 'Guide 16', 'msrp': 140, 'weight_oz': 9.4, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'PWRRUN', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'hurricane 24': {'name': 'Hurricane 24', 'msrp': 170, 'weight_oz': 11.4, 'drop_mm': 8, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 30, 'cushion_type': 'PWRRUN+', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'endorphin speed 4': {'name': 'Endorphin Speed 4', 'msrp': 170, 'weight_oz': 7.5, 'drop_mm': 8, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 30, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_rocker': True},
            'endorphin speed 3': {'name': 'Endorphin Speed 3', 'msrp': 170, 'weight_oz': 7.4, 'drop_mm': 8, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 30, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_rocker': True},
            'endorphin pro 4': {'name': 'Endorphin Pro 4', 'msrp': 225, 'weight_oz': 7.0, 'drop_mm': 8, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 31, 'cushion_type': 'PWRRUN HG', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'endorphin pro 3': {'name': 'Endorphin Pro 3', 'msrp': 225, 'weight_oz': 6.8, 'drop_mm': 8, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 31, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'endorphin elite': {'name': 'Endorphin Elite', 'msrp': 275, 'weight_oz': 6.5, 'drop_mm': 8, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 32, 'cushion_type': 'PWRRUN HG', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            # Trail
            'peregrine 14': {'name': 'Peregrine 14', 'msrp': 140, 'weight_oz': 9.7, 'drop_mm': 4, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 25, 'cushion_type': 'PWRRUN', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'peregrine 13': {'name': 'Peregrine 13', 'msrp': 140, 'weight_oz': 9.5, 'drop_mm': 4, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 25, 'cushion_type': 'PWRRUN', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'xodus ultra 2': {'name': 'Xodus Ultra 2', 'msrp': 180, 'weight_oz': 11.5, 'drop_mm': 4, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 33, 'cushion_type': 'PWRRUN PB', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'blaze tr': {'name': 'Blaze TR', 'msrp': 150, 'weight_oz': 10.6, 'drop_mm': 4, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 27, 'cushion_type': 'PWRRUN', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
        'new balance': {
            # Neutral Road
            'fresh foam 1080v14': {'name': 'Fresh Foam 1080v14', 'msrp': 165, 'weight_oz': 10.1, 'drop_mm': 6, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'fresh foam 1080v13': {'name': 'Fresh Foam 1080v13', 'msrp': 165, 'weight_oz': 10.0, 'drop_mm': 6, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'fresh foam 880v14': {'name': 'Fresh Foam 880v14', 'msrp': 135, 'weight_oz': 9.6, 'drop_mm': 10, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 22, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'fresh foam 880v13': {'name': 'Fresh Foam 880v13', 'msrp': 135, 'weight_oz': 9.5, 'drop_mm': 10, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 22, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'fuelcell rebel v4': {'name': 'FuelCell Rebel v4', 'msrp': 140, 'weight_oz': 7.9, 'drop_mm': 6, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 28, 'cushion_type': 'FuelCell', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'fuelcell rebel v3': {'name': 'FuelCell Rebel v3', 'msrp': 140, 'weight_oz': 7.8, 'drop_mm': 6, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 28, 'cushion_type': 'FuelCell', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'fuelcell propel v5': {'name': 'FuelCell Propel v5', 'msrp': 110, 'weight_oz': 8.8, 'drop_mm': 6, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 25, 'cushion_type': 'FuelCell', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            # Stability Road
            '860v14': {'name': '860v14', 'msrp': 140, 'weight_oz': 10.5, 'drop_mm': 10, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            '860v13': {'name': '860v13', 'msrp': 140, 'weight_oz': 10.3, 'drop_mm': 10, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'fresh foam vongo v6': {'name': 'Fresh Foam Vongo v6', 'msrp': 165, 'weight_oz': 10.3, 'drop_mm': 6, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 28, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'fuelcell supercomp elite v4': {'name': 'FuelCell SuperComp Elite v4', 'msrp': 275, 'weight_oz': 7.4, 'drop_mm': 4, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 35, 'cushion_type': 'FuelCell', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'fuelcell supercomp trainer v2': {'name': 'FuelCell SuperComp Trainer v2', 'msrp': 180, 'weight_oz': 8.6, 'drop_mm': 6, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 31, 'cushion_type': 'FuelCell', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_rocker': True},
            'fuelcell sc elite v3': {'name': 'FuelCell SC Elite v3', 'msrp': 230, 'weight_oz': 6.9, 'drop_mm': 4, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 35, 'cushion_type': 'FuelCell', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'fuelcell rc elite v2': {'name': 'FuelCell RC Elite v2', 'msrp': 225, 'weight_oz': 6.6, 'drop_mm': 6, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 29, 'cushion_type': 'FuelCell', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True},
            # Trail
            'fresh foam hierro v8': {'name': 'Fresh Foam Hierro v8', 'msrp': 145, 'weight_oz': 11.4, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'fresh foam hierro v7': {'name': 'Fresh Foam Hierro v7', 'msrp': 145, 'weight_oz': 11.2, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'fuelcell summit unknown v4': {'name': 'FuelCell Summit Unknown v4', 'msrp': 160, 'weight_oz': 9.8, 'drop_mm': 4, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 27, 'cushion_type': 'FuelCell', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'fresh foam more trail v3': {'name': 'Fresh Foam More Trail v3', 'msrp': 150, 'weight_oz': 12.0, 'drop_mm': 4, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 34, 'cushion_type': 'Fresh Foam X', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
        'on': {
            # Neutral Road
            'cloudmonster 2': {'name': 'Cloudmonster 2', 'msrp': 180, 'weight_oz': 10.2, 'drop_mm': 6, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Helion', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'cloudmonster': {'name': 'Cloudmonster', 'msrp': 170, 'weight_oz': 10.0, 'drop_mm': 6, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Helion', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'cloudsurfer 7': {'name': 'Cloudsurfer 7', 'msrp': 160, 'weight_oz': 8.8, 'drop_mm': 10, 'stack_height_heel_mm': 36, 'stack_height_forefoot_mm': 26, 'cushion_type': 'Helion', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'cloudsurfer': {'name': 'Cloudsurfer', 'msrp': 160, 'weight_oz': 8.6, 'drop_mm': 10, 'stack_height_heel_mm': 36, 'stack_height_forefoot_mm': 26, 'cushion_type': 'Helion', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral', 'has_rocker': True},
            'cloudflow 4': {'name': 'Cloudflow 4', 'msrp': 160, 'weight_oz': 8.3, 'drop_mm': 6, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 25, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'cloudswift 4': {'name': 'Cloudswift 4', 'msrp': 150, 'weight_oz': 9.2, 'drop_mm': 8, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'cloud 5': {'name': 'Cloud 5', 'msrp': 150, 'weight_oz': 8.8, 'drop_mm': 8, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 20, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'cloudrunner 2': {'name': 'Cloudrunner 2', 'msrp': 150, 'weight_oz': 9.5, 'drop_mm': 10, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 22, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            # Stability Road
            'cloudstratus 3': {'name': 'Cloudstratus 3', 'msrp': 170, 'weight_oz': 10.1, 'drop_mm': 6, 'stack_height_heel_mm': 36, 'stack_height_forefoot_mm': 30, 'cushion_type': 'Helion', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            'cloudace': {'name': 'Cloudace', 'msrp': 190, 'weight_oz': 11.0, 'drop_mm': 10, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'cloudboom echo 3': {'name': 'Cloudboom Echo 3', 'msrp': 280, 'weight_oz': 7.4, 'drop_mm': 9, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Helion HF', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'cloudprime': {'name': 'Cloudprime', 'msrp': 300, 'weight_oz': 6.8, 'drop_mm': 10, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Helion HF', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            # Trail
            'cloudultra 2': {'name': 'Cloudultra 2', 'msrp': 190, 'weight_oz': 10.4, 'drop_mm': 8, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Helion', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'cloudventure': {'name': 'Cloudventure', 'msrp': 160, 'weight_oz': 9.5, 'drop_mm': 6, 'stack_height_heel_mm': 26, 'stack_height_forefoot_mm': 20, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'cloudvista 2': {'name': 'Cloudvista 2', 'msrp': 170, 'weight_oz': 10.0, 'drop_mm': 8, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 22, 'cushion_type': 'Helion', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
        'altra': {
            # Neutral Road (Zero Drop)
            'torin 7': {'name': 'Torin 7', 'msrp': 150, 'weight_oz': 10.2, 'drop_mm': 0, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 30, 'cushion_type': 'Altra EGO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'torin 6': {'name': 'Torin 6', 'msrp': 145, 'weight_oz': 10.0, 'drop_mm': 0, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 30, 'cushion_type': 'Altra EGO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'escalante 4': {'name': 'Escalante 4', 'msrp': 140, 'weight_oz': 8.2, 'drop_mm': 0, 'stack_height_heel_mm': 24, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Altra EGO', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'escalante 3': {'name': 'Escalante 3', 'msrp': 140, 'weight_oz': 8.0, 'drop_mm': 0, 'stack_height_heel_mm': 24, 'stack_height_forefoot_mm': 24, 'cushion_type': 'Altra EGO', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'rivera 4': {'name': 'Rivera 4', 'msrp': 130, 'weight_oz': 8.1, 'drop_mm': 0, 'stack_height_heel_mm': 26, 'stack_height_forefoot_mm': 26, 'cushion_type': 'Altra EGO', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'paradigm 7': {'name': 'Paradigm 7', 'msrp': 170, 'weight_oz': 11.5, 'drop_mm': 0, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 32, 'cushion_type': 'Altra EGO MAX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            'via olympus 2': {'name': 'Via Olympus 2', 'msrp': 180, 'weight_oz': 10.8, 'drop_mm': 0, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 33, 'cushion_type': 'Altra EGO MAX', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'vanish carbon 2': {'name': 'Vanish Carbon 2', 'msrp': 260, 'weight_oz': 6.5, 'drop_mm': 0, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 33, 'cushion_type': 'Altra EGO PRO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True},
            # Trail (Zero Drop)
            'lone peak 8': {'name': 'Lone Peak 8', 'msrp': 150, 'weight_oz': 10.5, 'drop_mm': 0, 'stack_height_heel_mm': 25, 'stack_height_forefoot_mm': 25, 'cushion_type': 'Altra EGO', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'lone peak 7': {'name': 'Lone Peak 7', 'msrp': 145, 'weight_oz': 10.3, 'drop_mm': 0, 'stack_height_heel_mm': 25, 'stack_height_forefoot_mm': 25, 'cushion_type': 'Altra EGO', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'olympus 6': {'name': 'Olympus 6', 'msrp': 170, 'weight_oz': 11.4, 'drop_mm': 0, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 33, 'cushion_type': 'Altra EGO MAX', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'olympus 5': {'name': 'Olympus 5', 'msrp': 170, 'weight_oz': 11.2, 'drop_mm': 0, 'stack_height_heel_mm': 33, 'stack_height_forefoot_mm': 33, 'cushion_type': 'Altra EGO MAX', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'timp 5': {'name': 'Timp 5', 'msrp': 150, 'weight_oz': 10.8, 'drop_mm': 0, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Altra EGO', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'timp 4': {'name': 'Timp 4', 'msrp': 145, 'weight_oz': 10.6, 'drop_mm': 0, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 29, 'cushion_type': 'Altra EGO', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
            'superior 6': {'name': 'Superior 6', 'msrp': 130, 'weight_oz': 8.6, 'drop_mm': 0, 'stack_height_heel_mm': 21, 'stack_height_forefoot_mm': 21, 'cushion_type': 'Altra EGO', 'cushion_level': 'light', 'terrain': 'trail', 'subcategory': 'neutral'},
            'mont blanc': {'name': 'Mont Blanc', 'msrp': 180, 'weight_oz': 9.2, 'drop_mm': 0, 'stack_height_heel_mm': 30, 'stack_height_forefoot_mm': 30, 'cushion_type': 'Altra EGO MAX', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'racing'},
        },
        'adidas': {
            # Neutral Road
            'ultraboost light': {'name': 'Ultraboost Light', 'msrp': 190, 'weight_oz': 10.0, 'drop_mm': 10, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 21, 'cushion_type': 'Light BOOST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'ultraboost 23': {'name': 'Ultraboost 23', 'msrp': 190, 'weight_oz': 10.4, 'drop_mm': 10, 'stack_height_heel_mm': 31, 'stack_height_forefoot_mm': 21, 'cushion_type': 'BOOST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'supernova rise': {'name': 'Supernova Rise', 'msrp': 140, 'weight_oz': 10.6, 'drop_mm': 10, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 27, 'cushion_type': 'DREAMSTRIKE+', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'supernova 3': {'name': 'Supernova 3', 'msrp': 120, 'weight_oz': 10.8, 'drop_mm': 10, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 25, 'cushion_type': 'BOUNCE', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'adistar 3': {'name': 'Adistar 3', 'msrp': 150, 'weight_oz': 11.2, 'drop_mm': 12, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 27, 'cushion_type': 'REPETITOR+', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'solarglide 6': {'name': 'Solarglide 6', 'msrp': 140, 'weight_oz': 10.2, 'drop_mm': 10, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 24, 'cushion_type': 'BOOST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            # Stability Road
            'solarcontrol 2': {'name': 'Solarcontrol 2', 'msrp': 150, 'weight_oz': 10.8, 'drop_mm': 10, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 25, 'cushion_type': 'BOOST', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'supernova solution': {'name': 'Supernova Solution', 'msrp': 150, 'weight_oz': 11.0, 'drop_mm': 10, 'stack_height_heel_mm': 37, 'stack_height_forefoot_mm': 27, 'cushion_type': 'DREAMSTRIKE+', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'adizero boston 12': {'name': 'Adizero Boston 12', 'msrp': 160, 'weight_oz': 8.5, 'drop_mm': 6, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 33, 'cushion_type': 'LIGHTSTRIKE PRO', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'racing'},
            'adizero boston 11': {'name': 'Adizero Boston 11', 'msrp': 160, 'weight_oz': 8.3, 'drop_mm': 6, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 33, 'cushion_type': 'LIGHTSTRIKE PRO', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'racing'},
            'adizero adios pro 3': {'name': 'Adizero Adios Pro 3', 'msrp': 250, 'weight_oz': 7.6, 'drop_mm': 6, 'stack_height_heel_mm': 39, 'stack_height_forefoot_mm': 33, 'cushion_type': 'LIGHTSTRIKE PRO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'adizero prime x strung': {'name': 'Adizero Prime X Strung', 'msrp': 380, 'weight_oz': 8.0, 'drop_mm': 6, 'stack_height_heel_mm': 50, 'stack_height_forefoot_mm': 44, 'cushion_type': 'LIGHTSTRIKE PRO', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'adizero sl': {'name': 'Adizero SL', 'msrp': 110, 'weight_oz': 8.6, 'drop_mm': 8, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 26, 'cushion_type': 'LIGHTSTRIKE', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'adizero takumi sen 10': {'name': 'Adizero Takumi Sen 10', 'msrp': 180, 'weight_oz': 6.2, 'drop_mm': 6, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 22, 'cushion_type': 'LIGHTSTRIKE PRO', 'cushion_level': 'light', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True},
            # Trail
            'terrex agravic flow 2': {'name': 'Terrex Agravic Flow 2', 'msrp': 150, 'weight_oz': 10.5, 'drop_mm': 6, 'stack_height_heel_mm': 29, 'stack_height_forefoot_mm': 23, 'cushion_type': 'LIGHTSTRIKE', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'terrex speed ultra': {'name': 'Terrex Speed Ultra', 'msrp': 200, 'weight_oz': 9.0, 'drop_mm': 5, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 23, 'cushion_type': 'LIGHTSTRIKE PRO', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'racing', 'has_carbon_plate': True},
            'terrex free hiker 2': {'name': 'Terrex Free Hiker 2', 'msrp': 230, 'weight_oz': 13.5, 'drop_mm': 6, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 29, 'cushion_type': 'BOOST', 'cushion_level': 'max', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
        'mizuno': {
            # Neutral Road
            'wave rider 28': {'name': 'Wave Rider 28', 'msrp': 140, 'weight_oz': 9.7, 'drop_mm': 12, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 20, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'wave rider 27': {'name': 'Wave Rider 27', 'msrp': 140, 'weight_oz': 9.5, 'drop_mm': 12, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 20, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'neutral'},
            'wave sky 7': {'name': 'Wave Sky 7', 'msrp': 170, 'weight_oz': 11.5, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'MIZUNO ENERZY CORE', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            'wave neo ultra': {'name': 'Wave Neo Ultra', 'msrp': 180, 'weight_oz': 9.8, 'drop_mm': 8, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 32, 'cushion_type': 'MIZUNO ENERZY LITE', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'neutral'},
            # Stability Road
            'wave inspire 20': {'name': 'Wave Inspire 20', 'msrp': 145, 'weight_oz': 10.4, 'drop_mm': 12, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 22, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'wave inspire 19': {'name': 'Wave Inspire 19', 'msrp': 145, 'weight_oz': 10.2, 'drop_mm': 12, 'stack_height_heel_mm': 34, 'stack_height_forefoot_mm': 22, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'stability'},
            'wave horizon 7': {'name': 'Wave Horizon 7', 'msrp': 175, 'weight_oz': 12.0, 'drop_mm': 10, 'stack_height_heel_mm': 38, 'stack_height_forefoot_mm': 28, 'cushion_type': 'MIZUNO ENERZY CORE', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'stability'},
            # Racing
            'wave rebellion pro 2': {'name': 'Wave Rebellion Pro 2', 'msrp': 250, 'weight_oz': 7.5, 'drop_mm': 5, 'stack_height_heel_mm': 40, 'stack_height_forefoot_mm': 35, 'cushion_type': 'MIZUNO ENERZY LITE', 'cushion_level': 'max', 'terrain': 'road', 'subcategory': 'racing', 'has_carbon_plate': True, 'has_rocker': True},
            'wave rebellion flash 2': {'name': 'Wave Rebellion Flash 2', 'msrp': 155, 'weight_oz': 8.1, 'drop_mm': 8, 'stack_height_heel_mm': 35, 'stack_height_forefoot_mm': 27, 'cushion_type': 'MIZUNO ENERZY LITE', 'cushion_level': 'moderate', 'terrain': 'road', 'subcategory': 'racing'},
            'wave duel 3': {'name': 'Wave Duel 3', 'msrp': 130, 'weight_oz': 7.0, 'drop_mm': 8, 'stack_height_heel_mm': 24, 'stack_height_forefoot_mm': 16, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'light', 'terrain': 'road', 'subcategory': 'racing'},
            # Trail
            'wave mujin 10': {'name': 'Wave Mujin 10', 'msrp': 165, 'weight_oz': 11.8, 'drop_mm': 6, 'stack_height_heel_mm': 32, 'stack_height_forefoot_mm': 26, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'wave daichi 8': {'name': 'Wave Daichi 8', 'msrp': 140, 'weight_oz': 10.5, 'drop_mm': 8, 'stack_height_heel_mm': 28, 'stack_height_forefoot_mm': 20, 'cushion_type': 'MIZUNO ENERZY', 'cushion_level': 'moderate', 'terrain': 'trail', 'subcategory': 'neutral'},
            'wave ibuki 4': {'name': 'Wave Ibuki 4', 'msrp': 115, 'weight_oz': 10.8, 'drop_mm': 8, 'stack_height_heel_mm': 26, 'stack_height_forefoot_mm': 18, 'cushion_type': 'U4ic', 'cushion_level': 'light', 'terrain': 'trail', 'subcategory': 'neutral'},
        },
    }

    def __init__(self):
        self.client = httpx.Client(
            headers=self.HEADERS,
            timeout=60,
            follow_redirects=True
        )

    def get_shoe_specs(self, brand: str, model: str) -> Optional[ShoeSpecs]:
        """Get shoe specifications from catalog."""
        brand_lower = brand.lower().strip()
        model_lower = model.lower().strip()

        if brand_lower in self.SHOE_CATALOG:
            brand_catalog = self.SHOE_CATALOG[brand_lower]

            # Try exact match
            if model_lower in brand_catalog:
                return self._catalog_to_specs(brand, brand_catalog[model_lower])

            # Try partial match
            for key, data in brand_catalog.items():
                if model_lower in key or key in model_lower:
                    return self._catalog_to_specs(brand, data)

        return None

    def _catalog_to_specs(self, brand: str, data: Dict[str, Any]) -> ShoeSpecs:
        """Convert catalog entry to ShoeSpecs."""
        return ShoeSpecs(
            brand=brand,
            name=data['name'],
            msrp=Decimal(str(data.get('msrp'))) if data.get('msrp') else None,
            weight_oz=Decimal(str(data.get('weight_oz'))) if data.get('weight_oz') else None,
            drop_mm=Decimal(str(data.get('drop_mm'))) if data.get('drop_mm') is not None else None,
            stack_height_heel_mm=Decimal(str(data.get('stack_height_heel_mm'))) if data.get('stack_height_heel_mm') else None,
            stack_height_forefoot_mm=Decimal(str(data.get('stack_height_forefoot_mm'))) if data.get('stack_height_forefoot_mm') else None,
            cushion_type=data.get('cushion_type'),
            cushion_level=data.get('cushion_level'),
            terrain=data.get('terrain', 'road'),
            subcategory=data.get('subcategory'),
            has_carbon_plate=data.get('has_carbon_plate', False),
            has_rocker=data.get('has_rocker', False),
        )

    def get_all_shoes_for_brand(self, brand: str) -> List[ShoeSpecs]:
        """Get all shoes for a brand from the catalog."""
        brand_lower = brand.lower().strip()
        if brand_lower not in self.SHOE_CATALOG:
            return []

        return [
            self._catalog_to_specs(brand, data)
            for data in self.SHOE_CATALOG[brand_lower].values()
        ]

    def get_total_shoe_count(self) -> int:
        """Get total number of shoes in catalog."""
        return sum(len(shoes) for shoes in self.SHOE_CATALOG.values())

    def close(self):
        """Close the HTTP client."""
        self.client.close()
