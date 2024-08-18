"""Archeologist"""

from functools import partial, update_wrapper
from loguru import logger as log
from inspect import signature
import re
from collections import defaultdict

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from .utils import normalize
from ..api.person import Person, exc_to_person, person_deduplicate, person_ta, person_set_field, dict_to_person


RE_SET = re.compile(r"(\s|^)set\W")


class JSONorNoneResponse(JSONResponse):
    def render(self, content: any) -> bytes:
        if not content:
            self.status_code = status.HTTP_204_NO_CONTENT
            return None
        return super(JSONorNoneResponse, self).render(content)


class ExcavatorField:

    def __init__(self, excavator: dict, field: str, person: Person):
        self.excavator: dict = excavator
        self.field: str = field
        self.person: Person = person

    async def run(self) -> Person | None:
        if not self.excavator['person_param']:
            p_eligible = {
                k: v for k, v in self.person.items()
                if k in self.excavator['parameters'] & self.person.keys()
                }
            p_exc: Person = await self.excavator["endpoint"](**p_eligible)
        else:
            p_exc: Person = await self.excavator["endpoint"](self.person)

        log.debug(f"excavator {self.excavator['endpoint']} on {self.field} gave {p_exc}")

        if p_exc:
            p_exc.update(dict_to_person(p_exc))
            person_ta.validate_python(p_exc)

        return p_exc

    async def excavate(self) -> dict:
        upgraded = set()

        log.debug(f"excavating {self.field} with excavator {self.excavator}")
        p_exc: Person = await self.run()

        if not p_exc:
            return {}
        
        if "OptOut" in p_exc:
            upgraded.add("Optout")
            log.warning(f"{self.excavator['endpoint']} gave OptOut for {self.person}")
            return upgraded

        p_eligible = {
            k: v for k, v in p_exc.items()
            if (v and (
                self.excavator['catchall']
                or k in self.excavator['update']
                or k in self.excavator['insert']
                )
                )
        }

        upgraded = {
            k for k, v in p_eligible.items()
            if self.upgrade(k, v)
            }

        return upgraded

    def upgrade(self, k, v):
        modified = False

        # skip alternateName if same as name
        if k == "alternateName" and v == self.person.get("name"):
            log.debug(
                f"{self.excavator['endpoint']} does nothing - alternateName == name: {v}"
                )
        # real update
        elif k not in self.person:
            modified = True
            person_set_field(self.person, k, v)
            log.debug(f"{self.excavator['endpoint']} add {k} : {v}")
        elif self.person[k] == v:
            log.debug(
                f"{self.excavator['endpoint']} does nothing - existing value {k} : {v}"
            )
            return None
        elif k in self.excavator["update"] or self.excavator["catchall"]:
            modified = True
            person_set_field(self.person, k, v)
            log.debug(f"{self.excavator['endpoint']} update {k} : {v}")
        else:
            log.debug(
                f"{self.excavator['endpoint']} does nothing - already exists or insert mode {k} : {v}"
            )
        return modified


class Archeologist:
    """Enrich iteratively persons using excavators"""

    _ordered_elements: list = [
        "url",
        "sameAs",
        "email",
        "image",
        "description",
        "name",
    ]

    default_path: str = "/{operation}/{func_name}/{{{field}}}"

    def __init__(self, router: APIRouter = None):
        self.fields: set = set()
        self.excavators: dict = {k: [] for k in self._ordered_elements}
        self.router = router

        # we don't excavate again with the same excavator, the same field/value
        # so we keep an history of what field/value was used for what excavator

    async def person(self, person: dict) -> tuple[bool, dict]:
        """Transmute one person

        Args:
            person (dict): person to transmute

        Returns:
            bool, dict: succeed or not, enriched person
        """
        fields = list(person.keys() & self.fields)
        exc: dict = defaultdict(list)

        log.debug(f"excavating {fields} for {person}")

        modified = False
        # sync because we want to control the order of excavating fields
        for field in fields:
            log.debug(f"excavating {field}: {person.get(field)}")

            if field not in self.excavators:
                log.debug(f"no excavator for {field}")
                continue

            upgraded = set()
            for excavator in self.excavators[field]:
                # do not excavate twice the same field/value with the same excavator
                if (field, person[field]) in exc[excavator["endpoint"]]:
                    log.error(f"{excavator['endpoint']} already exc {field} with value {person[field]}")
                    continue
 
                exc[excavator["endpoint"]].append((field, person[field]))

                excavator_f = ExcavatorField(excavator, field, person)             
                upgraded.update(await excavator_f.excavate())

            modified = True if upgraded else modified

            # eligibility to excavate
            to_excavate = upgraded & self.fields
            if upgraded and to_excavate:
                fields.extend(to_excavate)
                log.debug(f"new fields to excavate: {to_excavate}")

        return modified, (person if modified else {})

    def add_route(self, excavator_func, excavator_param: dict, is_person_param: bool, route_kwargs: dict):
        route_param = {}
        route_param.update(route_kwargs)
        excavator_response_type_name = excavator_func.__annotations__['return'].__name__.lower()
        route_param.update({
            'path': self.default_path.format(
                # only works if the function has one and only one return type
                operation=excavator_response_type_name,
                field=excavator_param['field'],
                func_name=excavator_func.__name__,),
            'endpoint': update_wrapper(partial(exc_to_person, excavator_func), excavator_func),
            'response_model': (
                excavator_func.__annotations__['return']
                | None
                ),
            'response_class': JSONorNoneResponse,
            'responses': (
                {204: {
                    'description': "No results found.",
                    'model': None,
                    }
                 }),
            'methods': ['POST' if is_person_param else 'GET', ],
            'tags': (excavator_response_type_name, )
        })
        self.router.add_api_route(**route_param)
    
    def register(self, **kw):
        """register a function as a excavator

        Args:
            field (str): schema.org field to excavate
            update (set): fields updated or added by the excavator
            insert (set): fields inserted only by the excavator
            transmute (bool): if excavator is part of transmute, default to True

        Returns:
            function: excavator
        """

        def decorator(excavator_func):
            if kw['field'] not in self._ordered_elements:
                raise ValueError("This field can't be exc")

            # Check if this is dict/person
            parameters = signature(excavator_func).parameters

            # Register as excavator
            excavator_param = {
                'field': kw.pop('field'),
                'update': kw.pop('update', []),
                'insert': kw.pop('insert', []),
                'transmute': kw.pop('transmute', False),
                'endpoint': excavator_func,
                'parameters': parameters,
            }
            excavator_param['catchall'] = not excavator_param['insert'] and not excavator_param['update']

            is_person_param = any(param.annotation is dict for param in parameters.values())

            if is_person_param:
                excavator_param['person_param'] = True
            else:
                excavator_param['person_param'] = False

            # add to FastAPI Router
            if self.router:
                self.add_route(excavator_func, excavator_param, is_person_param, route_kwargs=kw)

            log.debug(f"add {excavator_func.__name__} to excavators with parameters: {excavator_param}")
            self.excavators[excavator_param['field']].append(excavator_param)
            self.fields.add(excavator_param['field'])
            return excavator_func

        return decorator
