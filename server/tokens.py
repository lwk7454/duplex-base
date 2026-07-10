"""LiveKit access-token generation for the English Tutor."""

from livekit import api

from config import LiveKitConfig


def make_token(
    config: LiveKitConfig,
    *,
    identity: str,
    room: str,
    name: str = "",
    can_publish: bool = True,
) -> str:
    """Build a short-lived JWT for a participant to join a room.

    Args:
        identity: unique participant identity (e.g. "tutor", "student-1234").
        room:     room name to join.
        name:     display name (optional).
        can_publish: mic/cam publish rights (False for the AI tutor in some setups).
    """
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=can_publish,
        can_subscribe=True,
        can_publish_data=True,
    )
    builder = (
        api.AccessToken(config.api_key, config.api_secret)
        .with_identity(identity)
        .with_grants(grants)
    )
    if name:
        builder = builder.with_name(name)
    return builder.to_jwt()
