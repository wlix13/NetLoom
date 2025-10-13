from typing import Literal

from providers.virtualbox import VirtualBoxProvider


def make_provider(name: Literal["virtualbox", "kvm", "container"], **kwargs):
    match name:
        case "virtualbox":
            return VirtualBoxProvider(**kwargs)
        case _:
            raise NotImplementedError(f"Provider {name!r} is not implemented yet")
