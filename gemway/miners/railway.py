"""Railway"""

from functools import partial, update_wrapper
from loguru import logger as log
from inspect import signature
import re
from collections import defaultdict

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from ..api.person import Person, miner_to_person, person_ta, person_set_field, dict_to_person


RE_SET = re.compile(r"(\s|^)set\W")


class JSONorNoneResponse(JSONResponse):
    def render(self, content: any) -> bytes:
        if not content:
            self.status_code = status.HTTP_204_NO_CONTENT
            return None
        return super(JSONorNoneResponse, self).render(content)



class MinerField:

    def __init__(self, miner: dict, field: str, person: Person):
        self.miner: dict = miner
        self.field: str = field
        self.person: Person = person

    async def run(self) -> Person | None:
        if not self.miner['person_param']:
            p_eligible = {
                k: v for k, v in self.person.items()
                if k in self.miner['parameters'] & self.person.keys()
                }
            p_mined: Person = await self.miner["endpoint"](**p_eligible)
        else:
            p_mined: Person = await self.miner["endpoint"](self.person)

        log.debug(f"miner {self.miner['endpoint']} on {self.field} gave {p_mined}")

        p_mined.update(dict_to_person(p_mined))
        person_ta.validate_python(p_mined)

        return p_mined

    async def mine(self):
        upgraded = set()

        log.debug(f"mining {self.field} with miner {self.miner}")
        p_mined: Person = await self.run()

        if "OptOut" in p_mined:
            upgraded.add("Optout")
            log.warning(f"{self.miner['endpoint']} gave OptOut for {self.person}")
            return upgraded

        p_eligible = {
            k: v for k, v in p_mined.items()
            if (v and (
                self.miner['catchall']
                or k in self.miner['update']
                or k in self.miner['insert']
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
                f"{self.miner['endpoint']} does nothing - alternateName == name: {v}"
                )
        # real update
        elif k not in self.person:
            modified = True
            person_set_field(self.person, k, v)
            log.debug(f"{self.miner['endpoint']} add {k} : {v}")
        elif self.person[k] == v:
            log.debug(
                f"{self.miner['endpoint']} does nothing - existing value {k} : {v}"
            )
            return None
        elif k in self.miner["update"] or self.miner["catchall"]:
            modified = True
            person_set_field(self.person, k, v)
            log.debug(f"{self.miner['endpoint']} update {k} : {v}")
        else:
            log.debug(
                f"{self.miner['endpoint']} does nothing - already exists or insert mode {k} : {v}"
            )
        return modified


class Railway:
    """Enrich iteratively persons using miners"""

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
        self.miners: dict = {k: [] for k in self._ordered_elements}
        self.router = router

        # we don't mine again with the same miner, the same field/value
        # so we keep an history of what field/value was used for what miner

    async def person(self, person: dict) -> tuple[bool, dict]:
        """Transmute one person

        Args:
            person (dict): person to transmute

        Returns:
            bool, dict: succeed or not, enriched person
        """
        fields = list(person.keys() & self.fields)
        mined: dict = defaultdict(list)

        log.debug(f"mining {fields} for {person}")

        modified = False
        # sync because we want to control the order of mining fields
        for field in fields:
            log.debug(f"mining {field}: {person.get(field)}")

            if field not in self.miners:
                log.debug(f"no miner for {field}")
                continue

            upgraded = set()
            for miner in self.miners[field]:
                # do not mine twice the same field/value with the same miner
                if (field, person[field]) in mined[miner["endpoint"]]:
                    log.error(f"{miner['endpoint']} already mined {field} with value {person[field]}")
                    continue
                
                mined[miner["endpoint"]].append((field, person[field]))

                miner_f = MinerField(miner, field, person)                
                upgraded.update(await miner_f.mine())

            modified = True if upgraded else modified

            # eligibility to mine
            to_mine = upgraded & self.fields
            if upgraded and to_mine:
                fields.extend(to_mine)
                log.debug(f"new fields to mine: {to_mine}")

        return modified, (person if modified else {})

    def add_route(self, miner_func, miner_param: dict, is_person_param: bool, route_kwargs: dict):
        route_param = {}
        route_param.update(route_kwargs)
        route_param.update({
            'path': self.default_path.format(
                operation="enrich",
                field=miner_param['field'],
                func_name=miner_func.__name__,),
            'endpoint': update_wrapper(partial(miner_to_person, miner_func), miner_func),
            'response_model': (
                miner_func.__annotations__['return']
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
        })
        self.router.add_api_route(**route_param)
    
    def register(self, **kw):
        """register a function as a miner

        Args:
            field (str): schema.org field to mine
            update (set): fields updated or added by the miner
            insert (set): fields inserted only by the miner
            transmute (bool): if miner is part of transmute, default to True

        Returns:
            function: miner
        """

        def decorator(miner_func):
            if not kw['field'] in self._ordered_elements:
                raise ValueError("This field can't be mined")

            # Check if this is dict/person
            parameters = signature(miner_func).parameters

            # Register as miner
            miner_param = {
                'field': kw.pop('field'),
                'update': kw.pop('update', []),
                'insert': kw.pop('insert', []),
                'transmute': kw.pop('transmute', False),
                'endpoint': miner_func,
                'parameters': parameters,
            }
            miner_param['catchall'] = not miner_param['insert'] and not miner_param['update']

            is_person_param = any(param.annotation is dict for param in parameters.values())

            if is_person_param:
                miner_param['person_param'] = True
            else:
                miner_param['person_param'] = False

            # add to FastAPI Router
            if self.router:
                self.add_route(miner_func, miner_param, is_person_param, route_kwargs=kw)

            log.debug(f"add {miner_func.__name__} to miners with parameters: {miner_param}")
            self.miners[miner_param['field']].append(miner_param)
            self.fields.add(miner_param['field'])
            return miner_func

        return decorator
