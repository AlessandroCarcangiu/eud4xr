# ruff: noqa

import os

import voluptuous as vol
import yaml

from homeassistant.const import CONF_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.storage import Store

from ..const import *

MARK_DONE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("name"): cv.string,
        vol.Required("type"): vol.In(["order", "sequence", "choice"]),
        vol.Optional("part_of"): cv.string,
    }
)


class TaskExpression:
    def __init__(self, hass):
        self.hass = hass
        self.sequences = None
        self.choices = None
        self.orders = None
        self.iterations = None
        self.conditionals = None

        self.AUTOMATIONS_FILE_PATH = os.path.join(
            hass.config.config_dir, "automations.yaml"
        )

    async def async_initialize(self):
        """Carica sequenze da file o crea file vuoto se manca"""
        await self._load_expressions_from_store()

    async def _load_expressions_from_store(self):
        store = Store(
            self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
        )
        data = await store.async_load() or {}
        expressions = data.get(CONF_TASK_MODELLING_EXPRESSIONS, {})

        self.sequences = {
            item["name"]: {
                "sequence": item["sequence"],
            }
            for item in expressions.get("sequences", [])
        }
        self.choices = {
            item["name"]: {
                "choice": item["choice"],
            }
            for item in expressions.get("choices", [])
        }
        self.orders = {
            item["name"]: {"order": item["order"]}
            for item in expressions.get("orders", [])
        }
        self.iterations = {
            item["name"]: {
                "iteration": item["iteration"],
            }
            for item in expressions.get("iterations", [])
        }
        self.conditionals = (
            {
                item["name"]: {
                    "conditional": item["conditional"],
                }
                for item in expressions.get("conditionals", [])
            }
            if "conditionals" in expressions
            else {}
        )

    async def get_expressions_from_store(self):
        """Restituisce le espressioni caricate nello store in formato json"""
        store = Store(
            self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
        )
        data = await store.async_load() or {}
        return data.get(CONF_TASK_MODELLING_EXPRESSIONS, {})

    async def _save_expressions_to_store(self):
        store = Store(
            self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
        )
        data = await store.async_load() or {}

        expressions = {
            "sequences": [
                {"name": name, "sequence": seq["sequence"]}
                for name, seq in self.sequences.items()
            ],
            "orders": [
                {"name": name, "order": ords["order"]}
                for name, ords in self.orders.items()
            ],
            "choices": [
                {"name": name, "choice": ch["choice"]}
                for name, ch in self.choices.items()
            ],
            "iterations": [
                {"name": name, "iteration": it["iteration"]}
                for name, it in self.iterations.items()
            ],
            "conditionals": [
                {"name": name, "conditional": cond["conditional"]}
                for name, cond in (self.conditionals or {}).items()
            ],
        }
        data[CONF_TASK_MODELLING_EXPRESSIONS] = expressions

        await store.async_save(data)

    def _load_automations_from_file(self):
        if not os.path.exists(self.AUTOMATIONS_FILE_PATH):
            with open(self.AUTOMATIONS_FILE_PATH, "w") as f:
                yaml.safe_dump({}, f)
            return {}

        with open(self.AUTOMATIONS_FILE_PATH) as f:
            automations = yaml.safe_load(f) or {}

        return automations

    def _write_automations(self, automations):
        with open(self.AUTOMATIONS_FILE_PATH, "w") as f:
            yaml.safe_dump(automations, f, sort_keys=False)

    async def create_sequence(self, name, sequence):
        if self.sequences is None:
            await self.async_initialize()

        if name in self.sequences:
            # se la sequenza esiste già viene eliminata per poter essere ricreata
            await self.delete_sequence(name)

        if not isinstance(sequence, list) or len(sequence) < 2:
            raise ValueError("La sequenza deve contenere almeno due elementi.")

        processed_sequence = await self._process_and_validate_sequence(sequence)

        sequence_processed = []
        for elemento in processed_sequence:
            if isinstance(elemento, dict) and "choice" in elemento:
                choice_name = elemento["name"]
                choice_list = elemento["choice"]

                if choice_name in self.choices:
                    raise ValueError(
                        f"Il nome della scelta '{choice_name}' è già in uso"
                    )

                self.choices[choice_name] = {
                    "choice": choice_list,
                }

                sequence_processed.append(f"choice.{choice_name}")
            elif isinstance(elemento, dict) and "order" in elemento:
                order_name = elemento["name"]
                order_list = elemento["order"]

                if order_name in self.orders:
                    raise ValueError(f"Il nome dell'ordine '{order_name}' è già in uso")

                self.orders[order_name] = {
                    "order": order_list,
                }

                sequence_processed.append(f"order.{order_name}")
            else:
                sequence_processed.append(elemento)

        self.sequences[name] = {
            "sequence": sequence_processed,
        }

        prev = False

        for i, element in enumerate(sequence):
            next_element = sequence[i + 1] if i < len(sequence) - 1 else None
            # automation
            if isinstance(element, str):
                await self._automation_to_sequence(
                    element, next_element, name, i == 0 or prev
                )
            # choice
            elif isinstance(element, dict) and "choice" in element:
                await self._choice_to_sequence(
                    element["choice"],
                    next_element,
                    name,
                    i == 0 or prev,
                    element["name"],
                )
            # order
            elif isinstance(element, dict) and "order" in element:
                await self._order_to_sequence(
                    element["order"], element["name"], name, i == 0 or prev
                )
                if next_element:
                    if isinstance(next_element, str):
                        await self._add_condition_to_automation(
                            next_element,
                            {
                                "condition": "state",
                                "entity_id": f"sensor.{element['name']}",
                                "state": str(len(element["order"])),
                            },
                            f"sequence.{name}",
                        )
                    elif isinstance(next_element, dict) and "choice" in next_element:
                        for choice_automation in next_element["choice"]:
                            await self._add_condition_to_automation(
                                choice_automation,
                                {
                                    "condition": "state",
                                    "entity_id": f"sensor.{element['name']}",
                                    "state": str(len(element["order"])),
                                },
                                f"sequence.{name}",
                            )
                    elif isinstance(next_element, dict) and "order" in next_element:
                        for order_automation in next_element["order"]:
                            await self._add_condition_to_automation(
                                order_automation,
                                {
                                    "condition": "state",
                                    "entity_id": f"sensor.{element['name']}",
                                    "state": str(len(element["order"])),
                                },
                                f"sequence.{name}",
                            )
            prev = isinstance(element, dict) and "order" in element

        # una volta creata la sequenza, si aggiungono le condizioni alle automazioni
        await self._save_expressions_to_store()

    async def _add_condition_to_automation(
        self, automation_entity_id, condition, alias
    ):
        source_alias = automation_entity_id.split(".")[-1]
        automations = await self.hass.async_add_executor_job(
            self._load_automations_from_file
        )
        for automation in automations:
            if automation.get("alias") == source_alias:
                if "condition" not in automation:
                    automation["condition"] = []

                def get_target_entities(target):
                    if isinstance(target, str):
                        if target.startswith("choice."):
                            choice_name = target.split(".", 1)[1]
                            if choice_name in self.choices:
                                return self.choices[choice_name]["choice"]
                            return []
                        if target.startswith("order."):
                            order_name = target.split(".", 1)[1]
                            if order_name in self.orders:
                                return self.orders[order_name]["order"]
                            return []
                        # Target singolo
                        return [target]
                    if isinstance(target, list):
                        return target
                    return []

                condition_entity_id = condition.get("entity_id")

                if condition_entity_id:
                    target_entities = get_target_entities(condition_entity_id)
                    for entity_id in target_entities:
                        condition_exists = any(
                            isinstance(existing_condition, dict)
                            and existing_condition.get("alias") == alias
                            and existing_condition.get("entity_id") == entity_id
                            for existing_condition in automation["condition"]
                        )
                        if not condition_exists:
                            condition_with_alias = condition.copy()
                            condition_with_alias["alias"] = alias
                            condition_with_alias["entity_id"] = entity_id
                            automation["condition"].append(condition_with_alias)
                else:
                    condition_exists = any(
                        isinstance(existing_condition, dict)
                        and existing_condition.get("alias") == alias
                        for existing_condition in automation["condition"]
                    )

                    if not condition_exists:
                        condition_with_alias = condition.copy()
                        condition_with_alias["alias"] = alias
                        automation["condition"].append(condition_with_alias)
                break
        else:
            raise ValueError(
                f"L'automazione '{automation_entity_id}' non è stata trovata."
            )

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _process_and_validate_sequence(self, sequence):
        processed = []
        for element in sequence:
            if isinstance(element, str):
                processed.append(element)
            elif isinstance(element, dict):
                if "choice" in element:
                    if (
                        not isinstance(element["choice"], list)
                        or len(element["choice"]) < 2
                    ):
                        raise ValueError(
                            "Una scelta deve contenere almeno due automazioni"
                        )
                    if not all(isinstance(item, str) for item in element["choice"]):
                        raise ValueError(
                            "Tutti gli elementi di una scelta devono essere automazioni (stringhe)"
                        )
                    processed.append(element)
                elif "order" in element:
                    if (
                        not isinstance(element["order"], list)
                        or len(element["order"]) < 2
                    ):
                        raise ValueError(
                            "Un ordine deve contenere almeno due automazioni"
                        )
                    if not all(isinstance(item, str) for item in element["order"]):
                        raise ValueError(
                            "Tutti gli elementi di un ordine devono essere automazioni (stringhe)"
                        )
                    processed.append(element)
                else:
                    raise ValueError("Elemento non riconosciuto nel dizionario.")
            else:
                raise ValueError(
                    "Gli elementi devono essere stringhe (automazioni) o dizionari con 'choice'"
                )

        return processed

    async def _automation_to_sequence(
        self, automation_id, next_element, sequence_name, is_first
    ):
        if not is_first:
            await self._deactivate_automation(automation_id)

        if next_element:
            await self._add_action_turn_on_to_automation(
                automation_id, next_element, sequence_name
            )
            await self._add_action_turn_on_to_automation(
                automation_id, next_element, sequence_name
            )

        await self._add_action_turn_off_to_automation(
            source=automation_id,
            target=automation_id,
            name=sequence_name,
            type_="sequence",
        )

        if is_first:
            await self._activate_automation(automation_id)

    async def _choice_to_sequence(
        self, choice_list, next_element, sequence_name, is_first, choice_name
    ):
        for i, automation_id in enumerate(choice_list):
            if not is_first:
                await self._deactivate_automation(automation_id)

            for j, other_automation in enumerate(choice_list):
                if i != j:
                    await self._add_action_turn_off_to_automation(
                        source=automation_id,
                        target=other_automation,
                        name=sequence_name,
                        type_="sequence",
                    )

            if next_element:
                await self._add_action_turn_on_to_automation(
                    source=automation_id,
                    target=next_element,
                    name=sequence_name,
                    type_="sequence",
                )
            await self._add_action_turn_off_to_automation(
                source=automation_id,
                target=automation_id,
                name=sequence_name,
                type_="sequence",
            )

        if is_first:
            for automation_id in choice_list:
                await self._activate_automation(automation_id)

    async def _order_to_sequence(
        self, order_list, order_name, sequence_name, is_first=False
    ):
        for automation_id in order_list:
            if not is_first:
                await self._deactivate_automation(automation_id)
            await self._add_action_increment_to_automation(
                automation_entity_id=automation_id,
                sensor_entity_id=f"sensor.{order_name}",
                alias=order_name,
            )
            await self._add_action_turn_off_to_automation(
                source=automation_id,
                target=automation_id,
                name=sequence_name,
                type_="order",
            )

            await self.create_order_independence_counter(order_name)

    async def create_choice(self, name, choice):
        if self.choices is None:
            await self.async_initialize()

        if name in self.choices:
            # Se la scelta esiste già, viene eliminata per poter essere ricreata
            await self.delete_choice(name)

        if not isinstance(choice, list) or not all(isinstance(a, str) for a in choice):
            raise ValueError(
                "La scelta deve essere una lista di ID automazioni (stringhe)."
            )
        if len(choice) < 2:
            raise ValueError("La scelta deve contenere almeno due automazioni.")

        self.choices[name] = {
            "choice": choice,
        }

        for i, automation_id in enumerate(choice):
            for j, other_id in enumerate(choice):
                if i != j:
                    await self._add_action_turn_off_to_automation(
                        source=automation_id, target=other_id, name=name, type_="choice"
                    )

        # Se la
        await self._save_expressions_to_store()

    async def create_order(self, name, order):
        if self.orders is None:
            await self.async_initialize()

        if name in self.orders:
            # Se l'ordine esiste già, viene eliminato per poter essere ricreato
            await self.delete_order(name)

        if not isinstance(order, list) or not all(isinstance(a, str) for a in order):
            raise ValueError(
                "L'ordine deve essere una lista di ID automazioni (stringhe)."
            )
        if len(order) < 2:
            raise ValueError("L'ordine deve contenere almeno due automazioni.")

        for automation_id in order:
            await self._add_action_turn_off_to_automation(
                source=automation_id,
                target=automation_id,
                name=name,
                type_="order",
            )
            await self._add_action_increment_to_automation(
                automation_entity_id=automation_id,
                sensor_entity_id=f"sensor.{name}",
                alias=name,
            )
        self.orders[name] = {
            "order": order,
        }
        await self.create_order_independence_counter(name)
        await self._save_expressions_to_store()

    async def create_order_independence_counter(self, name):
        await self.hass.async_create_task(
            self.hass.helpers.discovery.async_load_platform(
                "sensor",
                DOMAIN,
                {CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY: [name]},
                {},
            )
        )

    async def create_iteration(self, name, iteration):
        if self.iterations is None:
            await self.async_initialize()

        if name in self.iterations:
            await self.delete_iteration(name)

        if not isinstance(iteration, dict):
            raise ValueError(
                "Iteration deve essere un oggetto con 'n_steps' e 'expression'."
            )

        n_steps = iteration.get("n_steps")
        expression = iteration.get("expression")

        if not (isinstance(n_steps, int) and n_steps > 0):
            raise ValueError("'n_steps' deve essere un intero positivo.")
        if not (isinstance(expression, str) or isinstance(expression, dict)):
            raise ValueError(
                "'expression' deve essere una automazione (stringa) o una espressione (dict)."
            )

        if isinstance(expression, str):
            await self._add_condition_to_automation(
                automation_entity_id=expression,
                condition={
                    "condition": "numeric_state",
                    "entity_id": f"sensor.{name}",
                    "below": n_steps,
                },
                alias=f"iteration.{name}",
            )
            await self._add_action_increment_to_automation(
                automation_entity_id=expression,
                sensor_entity_id=f"sensor.{name}",
                alias=name,
            )

        await self.create_order_independence_counter(name)
        self.iterations[name] = {
            "iteration": iteration,
        }
        await self._save_expressions_to_store()

    async def create_conditional(self, name, conditional):
        if self.conditionals is None:
            await self.async_initialize()

        if name in self.conditionals:
            # Se la condizione esiste già, viene eliminata per poter essere ricreata
            await self.delete_conditional(name)
        if not isinstance(conditional, dict):
            raise ValueError("La condizione deve essere un dizionario.")

        if_trigger = conditional.get("if").get("trigger")
        else_trigger = conditional.get("else").get("trigger")
        if not isinstance(if_trigger, str):
            raise ValueError(
                "Il trigger 'if' deve essere una stringa che rappresenta un ID automazione."
            )
        if not isinstance(else_trigger, str):
            raise ValueError(
                "Il trigger 'else' deve essere una stringa che rappresenta un ID automazione."
            )

        for automation_id in [
            conditional.get("if").get("do"),
            conditional.get("else").get("do"),
        ]:
            await self._deactivate_automation(automation_id)
        await self._add_action_turn_off_to_automation(
            if_trigger, else_trigger, name, type_="conditional"
        )
        await self._add_action_turn_off_to_automation(
            else_trigger, if_trigger, name, type_="conditional"
        )
        for automation_id in conditional.get("if").get("do"):
            await self._add_action_turn_on_to_automation(
                if_trigger, automation_id, name, type_="conditional"
            )
        for automation_id in conditional.get("else").get("do"):
            await self._add_action_turn_on_to_automation(
                else_trigger, automation_id, name, type_="conditional"
            )
        for automation_id in [if_trigger, else_trigger]:
            await self._add_action_turn_off_to_automation(
                source=automation_id,
                target=automation_id,
                name=name,
                type_="conditional",
            )
        self.conditionals[name] = {
            "conditional": conditional,
        }

        await self._save_expressions_to_store()

    async def delete_sequence(self, name):
        if self.sequences is None:
            await self.async_initialize()

        if name not in self.sequences:
            raise ValueError(f"La sequenza '{name}' non esiste.")
        data = self.sequences[name]
        sequence = data["sequence"]
        for i, automation_id in enumerate(sequence):
            if "automation." in automation_id:
                if i < len(sequence) - 1:
                    await self._remove_action_from_automation(
                        source=automation_id,
                        service="automation.turn_on",
                        target=sequence[i + 1],
                    )
                await self._remove_action_from_automation(
                    source=automation_id,
                    service="automation.turn_off",
                    target=automation_id,
                )
                await self._remove_condition_from_automation(
                    source=automation_id, condition_alias=f"sequence.{name}"
                )
                await self._activate_automation(automation_id)
            elif "choice." in automation_id:
                choice_name = automation_id.split(".", 1)[1]
                if choice_name in self.choices:
                    choice = self.choices[choice_name]
                    for choice_automation in choice["choice"]:
                        await self._activate_automation(choice_automation)
                        if i < len(sequence) - 1:
                            await self._remove_action_from_automation(
                                source=choice_automation,
                                service="automation.turn_on",
                                target=sequence[i + 1],
                            )

                        await self._remove_condition_from_automation(
                            source=choice_automation, condition_alias=f"sequence.{name}"
                        )
                    await self.delete_choice(choice_name)

            elif "order." in automation_id:
                order_name = automation_id.split(".", 1)[1]
                if order_name in self.orders:
                    for order_automation in self.orders[order_name]["order"]:
                        await self._remove_condition_from_automation(
                            source=order_automation,
                            condition_alias=f"sequence.{name}",
                        )
                        await self._activate_automation(order_automation)
                    await self.delete_order(order_name)

        del self.sequences[name]
        await self._save_expressions_to_store()

    async def delete_choice(self, name):
        if self.choices is None:
            await self.async_initialize()

        if name not in self.choices:
            raise ValueError(f"La scelta '{name}' non esiste.")
        data = self.choices[name]
        choice = data["choice"]
        for i, automation_id in enumerate(choice):
            await self._remove_action_from_automation(
                source=automation_id,
                service="automation.turn_off",
                target=automation_id,
            )
            for j, other_id in enumerate(choice):
                if i != j:
                    await self._remove_action_from_automation(
                        source=automation_id,
                        service="automation.turn_off",
                        target=other_id,
                    )

        del self.choices[name]
        await self._save_expressions_to_store()

    async def delete_order(self, name):
        if self.orders is None:
            await self.async_initialize()

        if name not in self.orders:
            raise ValueError(f"L'ordine '{name}' non esiste.")
        data = self.orders[name]
        order = data["order"]
        for automation_id in order:
            await self._remove_action_from_automation(
                source=automation_id,
                service="automation.turn_off",
                target=automation_id,
            )
            await self._remove_action_from_automation(
                source=automation_id,
                service="eud4xr.increment_counter",
                target=f"sensor.{name}",
            )
        del self.orders[name]
        await self._save_expressions_to_store()
        await self.remove_counter_from_store(name)

    async def delete_iteration(self, name):
        if self.iterations is None:
            await self.async_initialize()

        if name not in self.iterations:
            raise ValueError(f"L'iterazione '{name}' non esiste.")
        data = self.iterations[name]
        iteration = data["iteration"]

        expression = (
            iteration.get("expression") if isinstance(iteration, dict) else iteration
        )

        if isinstance(expression, str):
            await self._remove_condition_from_automation(
                source=expression, condition_alias=f"iteration.{name}"
            )
            await self._remove_action_from_automation(
                source=expression,
                service="eud4xr.increment_counter",
                target=f"sensor.{name}",
            )

        del self.iterations[name]
        await self._save_expressions_to_store()
        await self.remove_counter_from_store(name)

    async def delete_conditional(self, name):
        if self.conditionals is None:
            await self.async_initialize()

        if name not in self.conditionals:
            raise ValueError(f"La condizione '{name}' non esiste.")
        data = self.conditionals[name]
        conditional = data["conditional"]

        if_trigger = conditional.get("if").get("trigger")
        else_trigger = conditional.get("else").get("trigger")

        for automation_id in [if_trigger, else_trigger]:
            await self._remove_action_from_automation(
                source=automation_id,
                service="automation.turn_off",
                target=automation_id,
            )

        await self._remove_action_from_automation(
            source=if_trigger,
            service="automation.turn_off",
            target=else_trigger,
        )
        await self._remove_action_from_automation(
            source=else_trigger,
            service="automation.turn_off",
            target=if_trigger,
        )

        for automation_id in conditional.get("if").get("do"):
            await self._remove_action_from_automation(
                source=if_trigger,
                service="automation.turn_on",
                target=automation_id,
            )
        for automation_id in conditional.get("else").get("do"):
            await self._remove_action_from_automation(
                source=else_trigger,
                service="automation.turn_on",
                target=automation_id,
            )

        for automation_id in [
            conditional.get("if").get("do"),
            conditional.get("else").get("do"),
            if_trigger,
            else_trigger,
        ]:
            await self._activate_automation(automation_id)

        del self.conditionals[name]
        await self._save_expressions_to_store()

    async def remove_counter_from_store(self, counter_name: str):
        entity_id = f"sensor.{counter_name}"

        entity_registry = async_get_entity_registry(self.hass)
        if entity_registry and entity_id in entity_registry.entities:
            entity_registry.async_remove(entity_id)

        data = self.hass.data.get(CONF_TASK_MODELLING_NAME, {})
        counters_list = data.get(CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY, [])

        if counter_name in counters_list:
            counters_list.remove(counter_name)

        data[CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY] = counters_list
        self.hass.data[CONF_TASK_MODELLING_NAME] = data

        store = Store(
            self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
        )

        stored_data = await store.async_load() or {}
        stored_counters_list = stored_data.get(
            CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY, []
        )

        if counter_name in stored_counters_list:
            stored_counters_list.remove(counter_name)

        stored_data[CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY] = (
            stored_counters_list
        )

        await store.async_save(stored_data)

    async def _deactivate_automation(self, automation_id):
        await self.hass.services.async_call(
            "automation", "turn_off", {"entity_id": automation_id}, blocking=True
        )

    async def _activate_automation(self, automation_id):
        await self.hass.services.async_call(
            "automation", "turn_on", {"entity_id": automation_id}, blocking=True
        )

    async def _add_action_turn_on_to_automation(
        self, source, target, name, type_="sequence"
    ):
        source_alias = source.split(".")[-1]
        automations = await self.hass.async_add_executor_job(
            self._load_automations_from_file
        )
        for automation in automations:
            if automation["alias"] == source_alias:
                if "action" not in automation:
                    automation["action"] = []

                # Determina i target effettivi basandosi sul tipo
                def get_target_entities(target):
                    if isinstance(target, str):
                        if target.startswith("choice."):
                            choice_name = target.split(".", 1)[1]
                            if choice_name in self.choices:
                                return self.choices[choice_name]["choice"]
                            return []
                        if target.startswith("order."):
                            order_name = target.split(".", 1)[1]
                            if order_name in self.orders:
                                return self.orders[order_name]["order"]
                            return []
                        return [target]
                    if isinstance(target, list):
                        return target
                    return []

                target_entities = get_target_entities(target)
                for entity_id in target_entities:
                    action_exists = any(
                        action.get("service") == "automation.turn_on"
                        and action.get("data", {}).get("entity_id") == entity_id
                        for action in automation["action"]
                    )
                    if not action_exists:
                        automation["action"].append(
                            {
                                "alias": f"{type_}.{name}",
                                "service": "automation.turn_on",
                                "data": {"entity_id": entity_id},
                            }
                        )
                break
        else:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")
        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _add_action_turn_off_to_automation(self, source, target, name, type_):
        source_alias = source.split(".")[-1]
        automations = await self.hass.async_add_executor_job(
            self._load_automations_from_file
        )

        for automation in automations:
            if automation["alias"] == source_alias:
                if "action" not in automation:
                    automation["action"] = []

                # Determina i target effettivi basandosi sul tipo
                def get_target_entities(target):
                    if isinstance(target, str):
                        if target.startswith("choice."):
                            choice_name = target.split(".", 1)[1]
                            if choice_name in self.choices:
                                return self.choices[choice_name]["choice"]
                            return []
                        if target.startswith("order."):
                            order_name = target.split(".", 1)[1]
                            if order_name in self.orders:
                                return self.orders[order_name]["order"]
                            return []
                        # Target singolo (incluso "automation")
                        return [target]
                    if isinstance(target, list):
                        return target
                    return []

                target_entities = get_target_entities(target)

                # Aggiungi azioni per ogni entity target solo se non già presente
                for entity_id in target_entities:
                    action_exists = any(
                        action.get("service") == "automation.turn_off"
                        and action.get("data", {}).get("entity_id") == entity_id
                        for action in automation["action"]
                    )

                    if not action_exists:
                        automation["action"].append(
                            {
                                "alias": f"{type_}.{name}",
                                "service": "automation.turn_off",
                                "data": {"entity_id": entity_id},
                            }
                        )
                break
        else:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _add_action_increment_to_automation(
        self, automation_entity_id: str, sensor_entity_id: str, alias: str
    ) -> None:
        source_alias = automation_entity_id.split(".")[-1]
        automations = await self.hass.async_add_executor_job(
            self._load_automations_from_file
        )

        for automation in automations:
            if automation.get("alias") == source_alias:
                automation.setdefault("action", [])

                action_exists = any(
                    action.get("service") == "eud4xr.increment_counter"
                    and action.get("data", {}).get("entity_id") == sensor_entity_id
                    for action in automation["action"]
                )

                if not action_exists:
                    automation["action"].append(
                        {
                            "alias": alias,
                            "service": "eud4xr.increment_counter",
                            "data": {"entity_id": sensor_entity_id},
                        }
                    )
                break
        else:
            raise ValueError(
                f"L'automazione '{automation_entity_id}' non è stata trovata."
            )

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _remove_action_from_automation(self, source, service, target=None):
        source_alias = source.split(".")[-1]
        automations = await self.hass.async_add_executor_job(
            self._load_automations_from_file
        )

        for automation in automations:
            if automation.get("alias") == source_alias:
                if "action" in automation:

                    def should_remove_action(act):
                        if act.get("service") != service:
                            return False

                        act_entity_id = act.get("data", {}).get("entity_id")

                        if target is None:
                            return True
                        if isinstance(target, list):
                            return act_entity_id in target
                        if isinstance(target, str):
                            if target.startswith("choice."):
                                choice_name = target.split(".", 1)[1]
                                return (
                                    choice_name in self.choices
                                    and act_entity_id
                                    in self.choices[choice_name]["choice"]
                                )
                            if target.startswith("order."):
                                order_name = target.split(".", 1)[1]
                                return (
                                    order_name in self.orders
                                    and act_entity_id
                                    in self.orders[order_name]["order"]
                                )
                            return act_entity_id == target
                        return False

                    automation["action"] = [
                        act
                        for act in automation["action"]
                        if not should_remove_action(act)
                    ]
                break
        else:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _remove_condition_from_automation(self, source, condition_alias):
        source_alias = source.split(".")[-1]

        automations = await self.hass.async_add_executor_job(
            self._load_automations_from_file
        )

        found = False
        for automation in automations:
            if automation.get("alias") == source_alias:
                if "condition" in automation:
                    original_count = len(automation["condition"])
                    automation["condition"] = [
                        cond
                        for cond in automation["condition"]
                        if cond.get("alias") != condition_alias
                    ]
                found = True
                break

        if not found:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def restore_expressions(self):
        """Ripristina lo stato delle automazioni secondo la logica delle sequenze."""
        if self.sequences is None or self.choices is None or self.orders is None:
            await self.async_initialize()

        for seq_name, seq_data in self.sequences.items():
            sequence = seq_data["sequence"]
            if not sequence:
                continue

            for idx, element in enumerate(sequence):
                prev_is_order = (
                    idx > 0
                    and isinstance(sequence[idx - 1], str)
                    and sequence[idx - 1].startswith("order.")
                )
                is_first = idx == 0

                activate = is_first or prev_is_order

                # Automazione singola
                if isinstance(element, str) and element.startswith("automation."):
                    if activate:
                        await self._activate_automation(element)
                    else:
                        await self._deactivate_automation(element)

                # Choice
                elif isinstance(element, str) and element.startswith("choice."):
                    choice_name = element.split(".", 1)[1]
                    if choice_name in self.choices:
                        for autom in self.choices[choice_name]["choice"]:
                            if activate:
                                await self._activate_automation(autom)
                            else:
                                await self._deactivate_automation(autom)

                # Order
                elif isinstance(element, str) and element.startswith("order."):
                    order_name = element.split(".", 1)[1]
                    if order_name in self.orders:
                        for autom in self.orders[order_name]["order"]:
                            if activate:
                                await self._activate_automation(autom)
                            else:
                                await self._deactivate_automation(autom)

    async def repair_automation_links(self, automation_id):
        """Method to repair automation links in sequences, choices, and orders."""
        if self.sequences is None:
            await self.async_initialize()

        for seq_name, seq_data in self.sequences.items():
            sequence = seq_data["sequence"]
            # Check if automation_id is in the sequence
            if automation_id in sequence:
                i = sequence.index(automation_id)
                next_element = sequence[i + 1] if i < len(sequence) - 1 else None
                prev_element = sequence[i - 1] if i > 0 else None
                is_first = i == 0
                prev_is_order = (
                    prev_element
                    and isinstance(prev_element, str)
                    and prev_element.startswith("order.")
                )
                # If the previous element is an order, add a condition to check the order count
                if prev_is_order:
                    order_name = prev_element.split(".", 1)[1]
                    if order_name in self.orders:
                        await self._add_condition_to_automation(
                            automation_id,
                            {
                                "condition": "state",
                                "entity_id": f"sensor.{order_name}",
                                "state": str(len(self.orders[order_name]["order"])),
                            },
                            f"sequence.{seq_name}",
                        )

                await self._automation_to_sequence(
                    automation_id, next_element, seq_name, is_first or prev_is_order
                )
                return
        # Check if automation_id is in any choice
        for choice_name, choice_data in self.choices.items():
            if automation_id in choice_data["choice"]:
                choice_list = choice_data["choice"]

                choice_in_sequence = False
                for seq_name, seq_data in self.sequences.items():
                    sequence = seq_data["sequence"]
                    choice_ref = f"choice.{choice_name}"
                    # Check if the choice reference is in the sequence
                    if choice_ref in sequence:
                        choice_in_sequence = True

                        i = sequence.index(choice_ref)
                        next_element = (
                            sequence[i + 1] if i < len(sequence) - 1 else None
                        )
                        prev_element = sequence[i - 1] if i > 0 else None
                        is_first = i == 0
                        prev_is_order = (
                            prev_element
                            and isinstance(prev_element, str)
                            and prev_element.startswith("order.")
                        )
                        # If the previous element is an order, add a condition to check the order count
                        if prev_is_order:
                            order_name = prev_element.split(".", 1)[1]
                            if order_name in self.orders:
                                await self._add_condition_to_automation(
                                    automation_id,
                                    {
                                        "condition": "state",
                                        "entity_id": f"sensor.{order_name}",
                                        "state": str(
                                            len(self.orders[order_name]["order"])
                                        ),
                                    },
                                    f"sequence.{seq_name}",
                                )

                        if not (is_first or prev_is_order):
                            await self._deactivate_automation(automation_id)

                        for other_automation in choice_list:
                            if automation_id != other_automation:
                                await self._add_action_turn_off_to_automation(
                                    source=automation_id,
                                    target=other_automation,
                                    name=seq_name,
                                    type_="choice",
                                )

                        if next_element:
                            await self._add_action_turn_on_to_automation(
                                source=automation_id,
                                target=next_element,
                                name=seq_name,
                                type_="sequence",
                            )

                        await self._add_action_turn_off_to_automation(
                            source=automation_id,
                            target=automation_id,
                            name=seq_name,
                            type_="choice",
                        )

                        if is_first or prev_is_order:
                            await self._activate_automation(automation_id)
                        break
                # If the automation is not in any sequence, turn it off
                if not choice_in_sequence:
                    for other_automation in choice_list:
                        if automation_id != other_automation:
                            await self._add_action_turn_off_to_automation(
                                source=automation_id,
                                target=other_automation,
                                name=choice_name,
                                type_="choice",
                            )
                return
        # Check if automation_id is in any order
        for order_name, order_data in self.orders.items():
            if automation_id in order_data["order"]:
                order_list = order_data["order"]
                # Check if the order is in any sequence
                order_in_sequence = False
                for seq_name, seq_data in self.sequences.items():
                    sequence = seq_data["sequence"]
                    order_ref = f"order.{order_name}"
                    # Check if the order reference is in the sequence
                    if order_ref in sequence:
                        order_in_sequence = True
                        i = sequence.index(order_ref)
                        next_element = (
                            sequence[i + 1] if i < len(sequence) - 1 else None
                        )
                        prev_element = sequence[i - 1] if i > 0 else None
                        is_first = i == 0
                        prev_is_order = (
                            prev_element
                            and isinstance(prev_element, str)
                            and prev_element.startswith("order.")
                        )
                        # If the previous element is an order, add a condition to check the order count
                        if prev_is_order:
                            prev_order_name = prev_element.split(".", 1)[1]
                            if prev_order_name in self.orders:
                                await self._add_condition_to_automation(
                                    automation_id,
                                    {
                                        "condition": "state",
                                        "entity_id": f"sensor.{prev_order_name}",
                                        "state": str(
                                            len(self.orders[prev_order_name]["order"])
                                        ),
                                    },
                                    f"sequence.{seq_name}",
                                )
                        # If the automation is the first in the sequence or follows an order, activate it
                        if not (is_first or prev_is_order):
                            await self._deactivate_automation(automation_id)

                        await self._add_action_increment_to_automation(
                            automation_entity_id=automation_id,
                            sensor_entity_id=f"sensor.{order_name}",
                            alias=order_name,
                        )

                        await self._add_action_turn_off_to_automation(
                            source=automation_id,
                            target=automation_id,
                            name=seq_name,
                            type_="order",
                        )
                        break
                # If the automation is not in any sequence, turn it off
                if not order_in_sequence:
                    await self._add_action_turn_off_to_automation(
                        source=automation_id,
                        target=automation_id,
                        name=order_name,
                        type_="order",
                    )
                    # If the automation is part of an order, add the increment action
                    await self._add_action_increment_to_automation(
                        automation_entity_id=automation_id,
                        sensor_entity_id=f"sensor.{order_name}",
                        alias=order_name,
                    )
                return

    # Funzioni di debug per mostrare le espressioni dello store
    async def reload_automations(self):
        """Helper method to reload automations."""
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def print_store(self):
        """Stampa il contenuto del file di archiviazione."""
        store = Store(
            self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
        )
        data = await store.async_load() or {}
        print(data)

    async def delete_store(self):
        """Elimina il file di archiviazione."""
        store = Store(
            self.hass, CONF_TASK_MODELLING_STORE_VERSION, CONF_TASK_MODELLING_STORE_NAME
        )
        data = {
            CONF_TASK_MODELLING_EXPRESSIONS: {},
            CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY: [],
        }
        await store.async_save(data)
        print("Store deleted successfully.")
