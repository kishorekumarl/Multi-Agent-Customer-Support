from typing import Literal

from pydantic import BaseModel, Field, model_validator


class UserInput(BaseModel):
    """The single customer identifier extracted from a user's message."""

    identifier: str | None = Field(
        default=None,
        description=(
            "Exactly one of: a numeric customer ID, an email address, or a phone "
            "number, copied exactly as the user wrote it. Null if the message "
            "contains none of these."
        ),
    )
    identifier_type: Literal["customer_id", "email", "phone"] | None = Field(
        default=None,
        description="What kind of value `identifier` is. Null if `identifier` is null.",
    )

    @model_validator(mode="after")
    def _both_or_neither(self) -> "UserInput":
        if (self.identifier is None) != (self.identifier_type is None):
            raise ValueError("identifier and identifier_type must be set together.")
        return self
