import json

import pytest

from app.models import Post, User


CONTENT_FRAGMENT = """
    ... on TextContentType { __typename body format wordCount }
    ... on ImageContentType { __typename url caption dimensions { width height aspectRatio } }
    ... on LinkContentType { __typename url title description }
"""

CREATE_POST_MUTATION = """
    mutation CreatePost($input: CreatePostInput!) {
        createPost(input: $input) {
            id
            title
            content { %s }
            userId
        }
    }
""" % CONTENT_FRAGMENT


class TestUserQueries:
    async def test_list_users_empty(self, client):
        resp = await client.post("/graphql", json={
            "query": "{ users { id name } }"
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["users"] == []

    async def test_create_user(self, client):
        resp = await client.post("/graphql", json={
            "query": """
                mutation {
                    createUser(input: { name: "Alice" }) {
                        id
                        name
                    }
                }
            """
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createUser"]
        assert data["name"] == "Alice"
        assert isinstance(data["id"], int)

    async def test_get_user_by_id(self, client, db_session):
        user = User(name="Bob")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": f'{{ user(id: {user.id}) {{ id name }} }}'
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["user"]
        assert data["name"] == "Bob"

    async def test_get_user_not_found(self, client):
        resp = await client.post("/graphql", json={
            "query": '{ user(id: 999) { id name } }'
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["user"] is None


class TestCreatePostWithTextContent:
    async def test_create_text_post(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "My Article",
                    "content": {"text": {"body": "Hello world", "format": "MARKDOWN"}},
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createPost"]
        assert data["title"] == "My Article"
        assert data["content"]["__typename"] == "TextContentType"
        assert data["content"]["body"] == "Hello world"
        assert data["content"]["format"] == "MARKDOWN"
        assert data["content"]["wordCount"] == 2

    async def test_text_post_default_format(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "Plain text",
                    "content": {"text": {"body": "Just text"}},
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createPost"]
        assert data["content"]["format"] == "PLAIN"


class TestCreatePostWithImageContent:
    async def test_create_image_post(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "Photo",
                    "content": {"image": {"url": "https://example.com/img.png", "caption": "Nice view"}},
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createPost"]
        assert data["content"]["__typename"] == "ImageContentType"
        assert data["content"]["url"] == "https://example.com/img.png"
        assert data["content"]["caption"] == "Nice view"
        assert data["content"]["dimensions"] is None

    async def test_create_image_post_with_dimensions(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "HD Photo",
                    "content": {
                        "image": {
                            "url": "https://example.com/hd.png",
                            "dimensions": {"width": 1920, "height": 1080},
                        }
                    },
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createPost"]
        assert data["content"]["__typename"] == "ImageContentType"
        assert data["content"]["dimensions"] == {"width": 1920, "height": 1080, "aspectRatio": "16:9"}

    async def test_image_post_without_caption(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "Quick snap",
                    "content": {"image": {"url": "https://example.com/snap.jpg"}},
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createPost"]
        assert data["content"]["caption"] is None


class TestCreatePostWithLinkContent:
    async def test_create_link_post(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "Cool link",
                    "content": {
                        "link": {
                            "url": "https://example.com",
                            "title": "Example",
                            "description": "An example site",
                        }
                    },
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["createPost"]
        assert data["content"]["__typename"] == "LinkContentType"
        assert data["content"]["url"] == "https://example.com"
        assert data["content"]["title"] == "Example"
        assert data["content"]["description"] == "An example site"


class TestPostContentValidation:
    async def test_multiple_content_fields_rejected(self, client, db_session):
        """@oneOf requires exactly one field to be set."""
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "Bad post",
                    "content": {
                        "text": {"body": "Hello"},
                        "image": {"url": "https://example.com/img.png"},
                    },
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        assert resp.json().get("errors") is not None

    async def test_missing_required_field_rejected(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": CREATE_POST_MUTATION,
            "variables": {
                "input": {
                    "title": "Bad post",
                    "content": {"text": {}},  # missing 'body'
                    "userId": user.id,
                }
            }
        })
        assert resp.status_code == 200
        assert resp.json().get("errors") is not None


class TestListPostsWithContent:
    async def test_list_posts_returns_typed_content(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        post = Post(
            title="Text post",
            content_json=json.dumps({"type": "text", "body": "Hi", "format": "plain"}),
            user_id=user.id,
        )
        db_session.add(post)
        db_session.commit()

        resp = await client.post("/graphql", json={
            "query": "{ posts { id title content { %s } } }" % CONTENT_FRAGMENT
        })
        assert resp.status_code == 200
        posts = resp.json()["data"]["posts"]
        assert len(posts) == 1
        assert posts[0]["content"]["__typename"] == "TextContentType"
        assert posts[0]["content"]["body"] == "Hi"
        assert posts[0]["content"]["wordCount"] == 1


class TestUserPostsRelation:
    async def test_user_has_posts(self, client, db_session):
        user = User(name="Alice")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        post1 = Post(title="First", content_json=json.dumps({"type": "text", "body": "a", "format": "plain"}), user_id=user.id)
        post2 = Post(title="Second", content_json=json.dumps({"type": "image", "url": "https://example.com/x.png"}), user_id=user.id)
        db_session.add_all([post1, post2])
        db_session.commit()

        resp = await client.post("/graphql", json={
            "query": f"""
                {{
                    user(id: {user.id}) {{
                        id
                        name
                        posts {{
                            id
                            title
                            content {{ {CONTENT_FRAGMENT} }}
                        }}
                    }}
                }}
            """
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["user"]
        assert data["name"] == "Alice"
        assert len(data["posts"]) == 2
        titles = {p["title"] for p in data["posts"]}
        assert titles == {"First", "Second"}

    async def test_user_with_no_posts(self, client, db_session):
        user = User(name="Bob")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = await client.post("/graphql", json={
            "query": f"""
                {{
                    user(id: {user.id}) {{
                        name
                        posts {{ id title }}
                    }}
                }}
            """
        })
        assert resp.status_code == 200
        data = resp.json()["data"]["user"]
        assert data["posts"] == []
