"""
Person Types
"""

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


def dict_to_person(person_dict: dict, setdefault=False, unsetvoid=False) -> Person:
    if setdefault:
        for k in Person.__annotations__.keys():
            is_k_set = RE_SET.match(str(Person.__annotations__[k]))
            if not is_k_set:
                continue
            elif k not in person_dict:
                person_dict[k] = set()
            elif not is_pure_iterable(person_dict[k]):
                person_dict[k] = {person_dict[k], }
    else:
        for k, v in person_dict.items():
            is_k_set = RE_SET.match(str(Person.__annotations__[k]))
            if is_k_set and not is_pure_iterable(v):
                person_dict[k] = {v, }

    # unefficient but clearer
    if unsetvoid:
        person_dict = person_unset_void(person_dict)

    return person_dict


def person_unset_void(person: Person) -> Person:
    return {k: v for k, v in person.items() if v is not None and v != {None, }}


def person_deduplicate(person: Person) -> Person:
    similar_fields = {
        "sameAs": "url",
        "alternateName": "name",
        }
    for field, original in similar_fields.items():
        if person.get(original) in person.get(field, ()):
            person[field].remove(person[original])
    return person

def is_pure_iterable(obj) -> bool:
    return hasattr(obj, "__iter__") and type(obj) is not str


async def miner_to_person(miner_func, *args, **kwargs) -> Person | None:
    result = await miner_func(*args, **kwargs)
    return dict_to_person(result, unsetvoid=True) if result else None


person_ta = TypeAdapter(Person)
person_request_ta = TypeAdapter(PersonRequest)
person_response_ta = TypeAdapter(PersonResponse)
