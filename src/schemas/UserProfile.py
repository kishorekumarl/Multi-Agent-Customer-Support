from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    """A customer's saved music tastes."""

    customer_id: int
    music_preferences: list[str] = Field(
        default_factory=list,
        description=(
            "Genres, artists, albums or tracks the customer has explicitly said they "
            "like. Empty if they stated none. Never include things they only asked about."
        ),
    )

    @field_validator("music_preferences")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        """Trim entries, drop blanks, and drop case-insensitive duplicates (first spelling wins)."""
        seen, cleaned = set(), []
        for value in values:
            value = value.strip()
            if value and value.casefold() not in seen:
                seen.add(value.casefold())
                cleaned.append(value)
        return cleaned
