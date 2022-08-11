import argparse
import asyncio
import sys

from pathlib import Path
import aiofiles
from aiocsv import AsyncDictWriter
import csv

import logging

import utils


class BrokenUrlInspector:

    def __init__(self, source_folder, output_file):
        self.source_folder = Path(source_folder)
        self.output_file_path = output_file
        self.logger = logging.getLogger(self.__class__.__name__)
        self.inspected_not_found_links = []
        self.inspected_invalid_links = []
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        self.output_file = await aiofiles.open(self.output_file_path, mode="w", encoding="utf-8", newline="")
        self.writer = AsyncDictWriter(self.output_file, ["file", "url", "reason"], restval="NULL", quoting=csv.QUOTE_ALL)
        await self.writer.writeheader()
        return self

    async def __aexit__(self, *exc_info):
        await self.output_file.close()
        [h.close() for h in self.logger.handlers]

    async def inspect_folder(self, folder_path: Path):
        self.logger.info(f"Inspecting folder '{folder_path}'")
        for path in folder_path.iterdir():
            if path.is_dir():
                asyncio.create_task(self.inspect_folder(path))
            else:
                asyncio.create_task(self.inspect_file(path))

    async def inspect_file(self, file_path: Path):
        if not file_path.name.endswith('.html'):
            return
        async with aiofiles.open(file_path) as f:
            content = await f.read()
            not_found_links = utils.get_not_found_links_for_html(content, file_path)
            for link in list(set(not_found_links)):
                async with self.lock:
                    if (str(file_path), link) not in self.inspected_not_found_links:
                        await self.writer.writerow({
                            "file": str(file_path),
                            "url": link,
                            "reason": "Not found"
                        })
                        self.inspected_not_found_links.append((str(file_path), link))

            unclosed_links = utils.get_unclosed_links_for_html(content)
            for unclosed_link in list(set(unclosed_links)):
                async with self.lock:
                    if (str(file_path), link) not in self.inspected_invalid_links:
                        await self.writer.writerow({
                            "file": str(file_path),
                            "url": unclosed_link,
                            "reason": "Unclosed tag"
                        })
                        self.inspected_invalid_links.append((str(file_path), link))

    async def run(self):
        await self.inspect_folder(self.source_folder)


async def main():
    async with BrokenUrlInspector(
        source_folder=args.source_folder,
        output_file=args.output_file
    ) as inspector:
        await inspector.run()
        while asyncio.all_tasks() - {asyncio.current_task()}:
            await asyncio.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source_folder', required=True)
    parser.add_argument('--output_file', required=True)

    args = parser.parse_args()

    asyncio.run(main())
