"""
Person Types
"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__license__ = "AGPL"

from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr, HttpUrl, constr
from typing_extensions import TypedDict
import re

RE_COUNTRY = r"^[A-Z]{2}$"
RE_LANGUAGE = r"^[a-z]{2}$"
RE_SET = re.compile(r"(\s|^)set\W")


class Person(TypedDict, total=False):
    name: str
    email: EmailStr
    homeLocation: set[str]
    alternateName: set[str]
    description: set[str]
    familyName: str
    givenName: str
    identifier: set[str]
    image: set[HttpUrl]
    jobTitle: set[str]
    knowsLanguage: set[constr(pattern=RE_LANGUAGE)]
    nationality: set[constr(pattern=RE_COUNTRY)]
    OptOut: bool
    sameAs: set[HttpUrl]
    url: HttpUrl
    workLocation: set[str]
    worksFor: set[str]


class PersonRequest(TypedDict):
    uid: str
    person: Person


class PersonResponse(TypedDict):
    status: bool
    person: Person | None


def person_set_field(person: Person, field: str, value: str | set) -> Person:
    """Set while transform field into set when the value or the dest is not set
    WARNING: only works with set/str

    Args:
        person (Person): person's dict
        field (str): field name to set
        value (str | set): value

    Returns:
        Person: person's dict
    """
    # quirky hack to check if one of annotation could be a set of something
    is_field_set = RE_SET.match(str(Person.__annotations__[field]))
    if is_field_set:
        if field not in person:
            person[field] = set()
        elif not type(person[field]) is set:
            person[field] = {person[field], }
        if type(value) is set:
            person[field] |= value
        else:
            person[field] |= {value, }
    else:
        person[field] = value

    return person


def dict_to_person(person_dict: dict) -> Person:
    for k, v in person_dict.items():
        is_k_set = RE_SET.match(str(Person.__annotations__[k]))
        if is_k_set and not is_pure_iterable(v):
            person_dict[k] = {v, }
    return person_dict


def is_pure_iterable(obj) -> bool:
    return hasattr(obj, "__iter__") and type(obj) is not str


person_ta = TypeAdapter(Person)
person_request_ta = TypeAdapter(PersonRequest)
person_response_ta = TypeAdapter(PersonResponse)
