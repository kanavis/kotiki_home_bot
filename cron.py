import asyncio

from kotiki.entrypoints.cron import cron_main


async def main():
    await cron_main()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Killed")
