import abc


class CronRunner(abc.ABC):
    @abc.abstractmethod
    async def run(self):
        pass
