import asyncio
import httpx
import time


async def main():
    payload = {
        "model": "qwen2.5:3b",
        "prompt": "Hello",
        "stream": False,
    }

    start = time.perf_counter()

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "http://127.0.0.1:11434/api/generate",
            json=payload,
        )

    end = time.perf_counter()

    print("Status:", response.status_code)
    print("Elapsed:", round(end - start, 2), "seconds")
    print(response.json()["response"])


asyncio.run(main())