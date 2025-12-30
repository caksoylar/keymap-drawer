"""Configuration models for layer stacking."""

from pydantic import BaseModel, Field


class CornerLayers(BaseModel):
    """Layer names for each corner position in stacked diagram.

    Each corner can display a different layer's key value:
    - tl (top-left): e.g., function layer
    - tr (top-right): e.g., system layer
    - bl (bottom-left): e.g., number layer
    - br (bottom-right): e.g., navigation layer
    """

    tl: str | None = Field(None, description="Top-left corner layer name")
    tr: str | None = Field(None, description="Top-right corner layer name")
    bl: str | None = Field(None, description="Bottom-left corner layer name")
    br: str | None = Field(None, description="Bottom-right corner layer name")


class StackConfig(BaseModel):
    """Configuration for layer stacking behavior.

    Controls which values to hide in corners and how to style held keys.
    """

    hidden_corner_legends: list[str] = Field(
        default_factory=list,
        description="Values to hide in corner positions (e.g., modifier symbols)",
    )
    hidden_held_legends: list[str] = Field(
        default_factory=list,
        description="Hold legend values to hide (e.g., 'sticky')",
    )
    hidden_shifted_legends: list[str] = Field(
        default_factory=list,
        description="Shifted legend values to hide",
    )
