import yarl
from adaptix import Retort, loader


def str_loader(value) -> str:
    if isinstance(value, str):
        return value
    elif isinstance(value, int):
        return str(value)
    else:
        raise TypeError("String expected, got {}".format(type(value)))


base_retort = Retort(
    recipe=[
        loader(str, str_loader),
        loader(yarl.URL, yarl.URL)
    ],
)
