s# Copyright 2022 Badreddine LEJMI.
# SPDX-License-Identifier: 	AGPL-3.0-or-later

"""Base Alchemist"""
__author__ = "Badreddine LEJMI <badreddine@ankaboot.fr>"
__copyright__ = "Ankaboot"
__license__ = "AGPL"

from loguru import logger as log
from fastapi import APIRouter
from ..api.person import Person, person_ta


class Alchemist:
    """Enrich iteratively persons using miners"""

    _ordered_elements: list = [
        "url",
        "sameAs",
        "email",
        "image",
        "description",
        "name",
    ]

    default_route: dict = {
        'methods': ["GET",],
        'path': "{operation}/{func_name}/{element}"
    }

    def __init__(self, router: APIRouter=None):
        self.elements: set = set()
        self.miners: dict = {k: [] for k in self._ordered_elements}
        self.router = router


        # we don't mine again with the same miner, the same element/value
        # so we keep an history of what element/value was used for what miner
        self._mined: dict = {}

    async def person(self, person: dict) -> tuple[bool, dict]:
        """Transmute one person

        Args:
            person (dict): person to transmute

        Returns:
            bool, dict: succeed or not, enriched person
        """
        elements = list(person.keys() & self.elements)

        log.debug(f"mining {elements} for {person}")

        modified = False
        # sync because we want to control the order of mining elements
        for el in elements:
            log.debug(f"mining {el}: {person.get(el)}")

            if el not in self.miners:
                log.debug(f"no miner for {el}")
                continue

            if el not in self._mined:
                self._mined[el] = {}

            for miner in self.miners[el]:
                # do not mine twice the same elemnt/value with the same miner
                if miner["func"] not in self._mined[el]:
                    self._mined[el] = {miner["func"]: []}
                elif person[el] in self._mined[el][miner["func"]]:
                    continue
                self._mined[el][miner["func"]].append(person[el])

                log.debug(f"mining {el} with miner {miner}")
                p_mined: Person = await miner["func"](person)
                if not p_mined:
                    continue

                person_ta.validate_python(p_mined)

                if "OptOut" in p_mined:
                    return False, {"OptOut": True}

                log.debug(f"miner {miner['func']} on {el} gave {p_mined}")

                for k, v in p_mined.items():
                    if not v:
                        continue
                    # eligibility to update
                    if (
                        not miner["catchall"]
                        and k not in miner["update"]
                        and k not in miner["insert"]
                    ):
                        continue

                    # skip alternateName if same as name
                    if k == "alternateName" and v == person.get("name"):
                        continue

                    # real update
                    if k not in person:
                        modified = True
                        person[k] = v
                        log.debug(f"{miner['func']} add {k} : {v}")
                    elif person[k] == v:
                        log.debug(
                            f"{miner['func']} does nothing - existing value {k} : {v}"
                        )
                        continue
                    elif k in miner["update"] or miner["catchall"]:
                        modified = True
                        # gymnastic to update/add set
                        if type(person[k]) is not set:
                            person[k] = {
                                person[k],
                            }
                        if type(v) is not set:
                            v = {
                                v,
                            }
                        person[k] |= v
                        log.debug(f"{miner['func']} update {k} : {v}")
                    else:
                        log.debug(
                            f"{miner['func']} does nothing - already exists or insert mode {k} : {v}"
                        )

                    # eligibility to mine
                    if k in self.elements:
                        elements.append(k)
                        log.debug(f"new element to mine: {k}")

        return modified, person if modified else None

    def register(self, **kw):
        """register a function as a miner for an element field

        Args:
            element (str): schema.org element to mine
            output (set): elements added by the miner

        Returns:
            function: miner
        """

        def decorator(miner_func):
            if kw["element"] in self._ordered_elements:
                
                miner_param = {
                    'element': kw.pop('element', []),
                    'update': kw.pop('update', []),
                    'insert': kw.pop('insert', []),
                    'transmute': kw.pop('transmute', False),
                }
                miner_param['catchall'] = not miner_param['insert'] and not miner_param['update']

                log.debug(f"add {miner_func} to miners with parameters: {kw}")
                self.miners[kw["element"]].append(miner_param)
                self.elements.add(kw["element"])


                if self.router:
                    route_param = self.default_route | kw
                    route_param['path'] = route_param['path'].format(
                            operation="transmute" if miner_param['transmute'] else "enrich",
                            element=miner_param['element'],
                            func_name=miner_func.__name__
                            )
                    route_para['endpoint'] = miner_func
                    self.router.add_api_route(**route_param)

            return miner_func

        return decorator
