from enum import Enum
from typing import Annotated, Literal, Union

import strawberry
from pydantic import BaseModel, Field


@strawberry.enum
class TextFormat(str, Enum):
    MARKDOWN = "markdown"
    PLAIN = "plain"


class TextContent(BaseModel):
    type: Literal["text"]
    body: str
    format: TextFormat = TextFormat.PLAIN


class ImageContent(BaseModel):
    type: Literal["image"]
    url: str
    caption: str | None = None


class LinkContent(BaseModel):
    type: Literal["link"]
    url: str
    title: str
    description: str | None = None


PostContent = Annotated[
    Union[TextContent, ImageContent, LinkContent],
    Field(discriminator="type"),
]
