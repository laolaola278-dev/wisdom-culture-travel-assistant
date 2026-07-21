"""Multi-modal stub: text-to-image search placeholder."""


def search_image(query: str, top_k: int = 5) -> list:
    return [
        {"name": f"{query}_sample_{i}", "type": "image",
         "source": "placeholder", "url": None}
        for i in range(top_k)
    ]
