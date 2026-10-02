from .base import Source
from .bma import BmaSource
from .bulletins import DisasterSource, OnwrSource
from .gistda import GistdaSource
from .thaiwater import ThaiWaterSource
from .tmd import TmdSource

# เรียงตามความสำคัญ — ThaiWater เป็นฐานหลัก
SOURCES: dict[str, type[Source]] = {
    cls.name: cls
    for cls in (ThaiWaterSource, GistdaSource, DisasterSource, OnwrSource, BmaSource, TmdSource)
}

__all__ = ["SOURCES", "Source"]
