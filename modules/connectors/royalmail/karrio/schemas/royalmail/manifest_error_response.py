import attr
import jstruct
import typing


@attr.s(auto_attribs=True)
class ErrorType:
    code: typing.Optional[str] = None
    description: typing.Optional[str] = None


@attr.s(auto_attribs=True)
class ManifestErrorResponseType:
    errors: typing.Optional[typing.List[ErrorType]] = jstruct.JList[ErrorType]
