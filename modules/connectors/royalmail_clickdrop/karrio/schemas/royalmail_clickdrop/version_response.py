import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class VersionResponseType:
    commit: typing.Optional[str] = None
    build: typing.Optional[str] = None
    release: typing.Optional[str] = None
    releaseDate: typing.Optional[str] = None
