"""
Telegram channel parser via Telethon (MTProto).
Reads public channel messages without needing to join.
"""


async def fetch_channel(channel_url: str, limit: int = 50) -> list[dict]:
    # TODO: Telethon client
    # client = TelegramClient(session_name, api_id, api_hash)
    # async for message in client.iter_messages(channel_url, limit=limit):
    #     yield {"text": message.text, "date": message.date, "url": ...}
    raise NotImplementedError
