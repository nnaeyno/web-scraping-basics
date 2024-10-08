import asyncio
import json
import os
import aiohttp
from data_processing import DataWriter, DataProcessor, DataFetcher


class AsyncDataFetcher(DataFetcher):
    async def fetch(self, url: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to fetch data from {url}")


def finalize(output_file: str):
    """Ensure that the JSON array is properly closed."""
    with open(output_file, 'rb+') as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size > 1:
            f.seek(size - 2)
            f.truncate()

    with open(output_file, 'a') as f:
        f.write("\n]")


class AsyncJSONDataWriter(DataWriter):
    def __init__(self):
        self.first_write = True

    async def write(self, data: dict, output_file: str):
        if not os.path.exists(output_file) or self.first_write:
            with open(output_file, 'w') as f:
                f.write("[\n")
            self.first_write = False

        with open(output_file, 'a') as f:
            json.dump(data, f, indent=4)
            f.write(",\n")


class AsyncDataProcessor(DataProcessor):
    def __init__(self, fetcher: AsyncDataFetcher, writer: DataWriter):
        super().__init__(fetcher, writer)
        self.lock = asyncio.Lock()

    async def worker(self, url: str, file_path: str):
        try:
            data = await self.fetcher.fetch(url)
            if data:
                async with self.lock:
                    await self.writer.write(data, file_path)
        except Exception as e:
            print(f"Error processing {url}: {e}")

    async def process(self, urls: list, output_file: str, max_workers: int = 16):
        tasks = []
        semaphore = asyncio.Semaphore(max_workers)

        async def limited_worker(assigned_url):
            async with semaphore:
                await self.worker(assigned_url, output_file)

        for url in urls:
            tasks.append(limited_worker(url))

        await asyncio.gather(*tasks)
        finalize(output_file)
