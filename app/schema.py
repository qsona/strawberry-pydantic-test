import dataclasses
from typing import Annotated, Optional, Union

import strawberry
import strawberry.experimental.pydantic
from pydantic import TypeAdapter

from app import database, models
from app.content_types import (
    ImageContent,
    ImageDimensions,
    LinkContent,
    PostContent,
    TextContent,
    TextFormat,
)


# --- Strawberry output types generated from Pydantic models ---
# Exclude 'type' field: in GraphQL, the union member is identified by __typename


@strawberry.experimental.pydantic.type(TextContent)
class TextContentType:
    body: strawberry.auto
    format: strawberry.auto

    @strawberry.field
    def word_count(self) -> int:
        return len(self.body.split())


@strawberry.experimental.pydantic.type(ImageDimensions)
class ImageDimensionsType:
    width: strawberry.auto
    height: strawberry.auto

    @strawberry.field
    def aspect_ratio(self) -> str:
        from math import gcd
        d = gcd(self.width, self.height)
        return f"{self.width // d}:{self.height // d}"


@strawberry.experimental.pydantic.type(ImageContent)
class ImageContentType:
    url: strawberry.auto
    caption: strawberry.auto
    dimensions: strawberry.auto


@strawberry.experimental.pydantic.type(LinkContent)
class LinkContentType:
    url: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto


PostContentType = Annotated[
    Union[TextContentType, ImageContentType, LinkContentType],
    strawberry.union("PostContentType"),
]


# --- Core GraphQL types ---

@strawberry.type(name="Post")
class PostType:
    id: int
    title: str
    user_id: int

    @strawberry.field
    def content(self) -> PostContentType:
        return TypeAdapter(PostContent).validate_python(self.content)


@strawberry.type(name="User")
class UserType:
    id: int
    name: str

    @strawberry.field
    def posts(self) -> list[PostType]:
        with database.SessionLocal() as session:
            return session.query(models.Post).filter(models.Post.user_id == self.id).all()


# --- Query ---


@strawberry.type
class Query:
    @strawberry.field
    def users(self) -> list[UserType]:
        with database.SessionLocal() as session:
            return session.query(models.User).all()

    @strawberry.field
    def user(self, id: int) -> Optional[UserType]:
        with database.SessionLocal() as session:
            return session.get(models.User, id)

    @strawberry.field
    def posts(self) -> list[PostType]:
        with database.SessionLocal() as session:
            return session.query(models.Post).all()


# --- Mutation ---


@strawberry.input
class CreateUserInput:
    name: str


@strawberry.input
class TextContentInput:
    body: str
    format: TextFormat = TextFormat.PLAIN


@strawberry.input
class ImageDimensionsInput:
    width: int
    height: int


@strawberry.input
class ImageContentInput:
    url: str
    caption: Optional[str] = None
    dimensions: Optional[ImageDimensionsInput] = None


@strawberry.input
class LinkContentInput:
    url: str
    title: str
    description: Optional[str] = None


@strawberry.input(one_of=True)
class PostContentInput:
    text: strawberry.Maybe[TextContentInput]
    image: strawberry.Maybe[ImageContentInput]
    link: strawberry.Maybe[LinkContentInput]


@strawberry.input
class CreatePostInput:
    title: str
    content: PostContentInput
    user_id: int


def _to_content_json(content: PostContentInput) -> str:
    """Convert a @oneOf PostContentInput to a validated JSON string for storage."""
    adapter = TypeAdapter(PostContent)
    for field in dataclasses.fields(content):
        maybe = getattr(content, field.name)
        if maybe is not None:
            data = dataclasses.asdict(maybe.value)
            data["type"] = field.name
            return adapter.validate_python(data).model_dump_json()
    raise ValueError("Exactly one content type must be provided")


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, input: CreateUserInput) -> UserType:
        with database.SessionLocal() as session:
            user = models.User(name=input.name)
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    @strawberry.mutation
    def create_post(self, input: CreatePostInput) -> PostType:
        content_json = _to_content_json(input.content)

        with database.SessionLocal() as session:
            post = models.Post(
                title=input.title,
                content_json=content_json,
                user_id=input.user_id,
            )
            session.add(post)
            session.commit()
            session.refresh(post)
            return post


schema = strawberry.Schema(query=Query, mutation=Mutation)
