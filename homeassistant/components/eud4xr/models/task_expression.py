import os
import yaml
import voluptuous as vol
from homeassistant.const import CONF_ENTITY_ID
import homeassistant.helpers.config_validation as cv

MARK_DONE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required("name"): cv.string,
        vol.Required("type"): vol.In(["order", "sequence", "choice"]),
    }
)


class TaskExpression:
    def __init__(self, hass):
        self.hass = hass
        self.sequences = None
        self.choices = None
        self.orders = None
        self.EXPRESSIONS_FILE_PATH = os.path.join(
            hass.config.config_dir, "expressions.yaml"
        )
        self.AUTOMATIONS_FILE_PATH = os.path.join(
            hass.config.config_dir, "automations.yaml"
        )

    async def async_initialize(self):
        """Carica sequenze da file o crea file vuoto se manca"""
        await self.hass.async_add_executor_job(self._load_expressions_from_file)

    def _load_expressions_from_file(self):
        if not os.path.exists(self.EXPRESSIONS_FILE_PATH):
            with open(self.EXPRESSIONS_FILE_PATH, "w") as f:
                yaml.safe_dump({}, f)
            return {}

        with open(self.EXPRESSIONS_FILE_PATH) as f:
            expressions = yaml.safe_load(f) or {}

        self.sequences = {
            item["name"]: {
                "sequence": item["sequence"],
                "state": item.get("state", {"done": False, "step": 0, "last": None}),
            }
            for item in expressions.get("sequences", [])
        }
        self.choices = {
            item["name"]: {
                "choice": item["choice"],
                "state": item.get("state", {"done": False, "selected": None}),
            }
            for item in expressions.get("choices", [])
        }
        self.orders = {
            item["name"]: {
                "order": item["order"],
                "total": item.get("total", len(item["order"])),
                "done": item.get("done", 0),
                "done_list": item.get("done_list", []),
                "state": item.get("state", {"done": False}),
            }
            for item in expressions.get("orders", [])
        }

    def _load_automations_from_file(self):
        if not os.path.exists(self.AUTOMATIONS_FILE_PATH):
            with open(self.AUTOMATIONS_FILE_PATH, "w") as f:
                yaml.safe_dump({}, f)
            return {}

        with open(self.AUTOMATIONS_FILE_PATH) as f:
            automations = yaml.safe_load(f) or {}

        return automations

    async def _save_expressions_to_file(self):
        await self.hass.async_add_executor_job(self._write_expressions_to_file)

    def _write_automations(self, automations):
        with open(self.AUTOMATIONS_FILE_PATH, "w") as f:
            yaml.safe_dump(automations, f, sort_keys=False)


    def _write_expressions_to_file(self):
        expressions = {}

        expressions["sequences"] = [
            {
                "name": name,
                "sequence": data["sequence"] if isinstance(data, dict) else data,
                "state": data.get("state", {"done": False, "step": 0, "last": None})
            }
            for name, data in self.sequences.items()
        ]

        expressions["choices"] = [
            {
                "name": name,
                "choice": data["choice"] if isinstance(data, dict) else data,
                "state": data.get("state", {"done": False, "selected": None})
            }
            for name, data in self.choices.items()
        ]

        expressions["orders"] = [
            {
                "name": name,
                "order": data["order"],
                "total": data.get("total", len(data["order"])),
                "done": data.get("done", 0),
                "done_list": data.get("done_list", []),
                "state": data.get("state", {"done": False})
            }
            for name, data in self.orders.items()
        ]

        with open(self.EXPRESSIONS_FILE_PATH, "w") as f:
            yaml.safe_dump(expressions, f, sort_keys=False)


    async def create_sequence(self, name, sequence):
        if self.sequences is None:
            await self.async_initialize()

        if name in self.sequences:
            raise ValueError(f"La sequenza '{name}' esiste già.")
        if not isinstance(sequence, list) or not all(
            isinstance(a, str) for a in sequence
        ):
            raise ValueError(
                "La sequenza deve essere una lista di ID automazioni (stringhe)."
            )
        if len(sequence) < 2:
            raise ValueError("La sequenza deve contenere almeno due automazioni.")

        # Salva come dizionario con sequence e state
        self.sequences[name] = {
            "sequence": sequence,
            "state": {"done": False, "step": 0, "last": None},
        }

        await self._save_expressions_to_file()

        for i, automation_id in enumerate(sequence):
            await self._deactivate_automation(automation_id)

            if i < len(sequence) - 1:
                next_automation = sequence[i + 1]
                await self._add_action_turn_on_to_automation(
                    source=automation_id, target=next_automation, name=name
                )
            await self._add_action_mark_done_to_automation(
                automation_entity_id=automation_id, name=name, type_="sequence"
            )

        await self._activate_automation(sequence[0])

        # await self.hass.services.async_call(
        #     "eud4xr",
        #     "update_state",
        #     {},
        #     blocking=False
        # )

    async def create_choice(self, name, choice):
        if self.choices is None:
            await self.async_initialize()

        if name in self.choices:
            raise ValueError(f"La scelta '{name}' esiste già.")
        if not isinstance(choice, list) or not all(isinstance(a, str) for a in choice):
            raise ValueError(
                "La scelta deve essere una lista di ID automazioni (stringhe)."
            )
        if len(choice) < 2:
            raise ValueError("La scelta deve contenere almeno due automazioni.")

        # Salva come dizionario con choice e state
        self.choices[name] = {
            "choice": choice,
            "state": {"done": False, "selected": None},
        }

        await self._save_expressions_to_file()

        for i, automation_id in enumerate(choice):
            for j, other_id in enumerate(choice):
                if i != j:
                    await self._add_action_turn_off_to_automation(
                        source=automation_id, target=other_id, name=name
                    )
            await self._add_action_mark_done_to_automation(
                automation_entity_id=automation_id, name=name, type_="choice"
            )



    async def create_order(self, name, order):
        if self.orders is None:
            await self.async_initialize()

        if name in self.orders:
            raise ValueError(f"L'ordine '{name}' esiste già.")
        if not isinstance(order, list) or not all(isinstance(a, str) for a in order):
            raise ValueError(
                "L'ordine deve essere una lista di ID automazioni (stringhe)."
            )
        if len(order) < 2:
            raise ValueError("L'ordine deve contenere almeno due automazioni.")

        self.orders[name] = {
            "order": order,
            "total": len(order),
            "done": 0,
            "done_list": [],
            "state": {"done": False},
        }

        await self._save_expressions_to_file()
        for automation_id in order:
            await self._add_action_mark_done_to_automation(
                automation_entity_id=automation_id, name=name, type_="order"
            )
        

    async def delete_sequence(self, name):
        if self.sequences is None:
            await self.async_initialize()

        if name not in self.sequences:
            raise ValueError(f"La sequenza '{name}' non esiste.")
        data = self.sequences[name]
        sequence = data["sequence"]
        for i, automation_id in enumerate(sequence):
            if i < len(sequence) - 1:
                await self._remove_action_from_automation(
                    source=automation_id,
                    service="automation.turn_on",
                )
            await self._remove_action_from_automation(
                source=automation_id,
                service="eud4xr.mark_done",
            )
            await self._restore_automation(automation_id)

        del self.sequences[name]
        await self._save_expressions_to_file()

    async def delete_choice(self, name):
        if self.choices is None:
            await self.async_initialize()

        if name not in self.choices:
            raise ValueError(f"La scelta '{name}' non esiste.")
        data = self.choices[name]
        choice = data["choice"]
        for i, automation_id in enumerate(choice):
            for j, _ in enumerate(choice):
                if i != j:
                    await self._remove_action_from_automation(
                        source=automation_id,
                        service="automation.turn_off",
                    )
                    await self._remove_action_from_automation(
                        source=automation_id,
                        service="eud4xr.mark_done",
                    )

        del self.choices[name]
        await self._save_expressions_to_file()

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
                service="eud4xr.mark_done",
            )

        del self.orders[name]
        await self._save_expressions_to_file()

    async def _deactivate_automation(self, automation_id):
        await self.hass.services.async_call(
            "automation", "turn_off", {"entity_id": automation_id}, blocking=True
        )

    async def _activate_automation(self, automation_id):
        await self.hass.services.async_call(
            "automation", "turn_on", {"entity_id": automation_id}, blocking=True
        )

    async def _restore_automation(self, automation_id):
        await self.hass.services.async_call(
            "automation", "turn_on", {"entity_id": automation_id}, blocking=True
        )

    async def _add_action_turn_on_to_automation(self, source, target, name):
        source_alias = source.split(".")[-1]
        automations = await self.hass.async_add_executor_job(self._load_automations_from_file)
        for automation in automations:
            if automation["alias"] == source_alias:
                if "action" not in automation:
                    automation["action"] = []
                automation["action"].append(
                    {
                        "alias": f"sequence.{name}",
                        "service": "automation.turn_on",
                        "data": {"entity_id": target},
                    }
                )
                break
        else:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")
        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _add_action_turn_off_to_automation(self, source, target, name):
        source_alias = source.split(".")[-1]
        automations = await self.hass.async_add_executor_job(self._load_automations_from_file)
        for automation in automations:
            if automation["alias"] == source_alias:
                if "action" not in automation:
                    automation["action"] = []
                automation["action"].append(
                    {
                        "alias": f"choice.{name}",
                        "service": "automation.turn_off",
                        "data": {"entity_id": target},
                    }
                )
                break
        else:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")
        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _add_action_mark_done_to_automation(
        self, automation_entity_id, name, type_
    ):
        source_alias = automation_entity_id.split(".")[-1]
        automations = await self.hass.async_add_executor_job(self._load_automations_from_file)

        for automation in automations:
            if automation.get("alias") == source_alias:
                if "action" not in automation:
                    automation["action"] = []

                alias_prefix = None
                if type_ == "order":
                    alias_prefix = f"order.{name}"
                elif type_ == "sequence":
                    alias_prefix = f"sequence.{name}"
                elif type_ == "choice":
                    alias_prefix = f"choice.{name}"
                else:
                    raise ValueError(
                        f"Tipo '{type_}' non riconosciuto. Usa 'order', 'sequence' o 'choice'."
                    )

                automation["action"].append(
                    {
                        "alias": alias_prefix,
                        "service": "eud4xr.mark_done",
                        "data": {
                            "entity_id": automation_entity_id,
                            "name": name,
                            "type": type_,
                        },
                    }
                )
                break
        else:
            raise ValueError(
                f"L'automazione '{automation_entity_id}' non è stata trovata."
            )

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    async def _remove_action_from_automation(self, source, service):
        source_alias = source.split(".")[-1]
        automations = await self.hass.async_add_executor_job(self._load_automations_from_file)
        found = False
        for automation in automations:
            if automation.get("alias") == source_alias:
                if "action" in automation:
                    automation["action"] = [
                        act
                        for act in automation["action"]
                        if act.get("service") != service
                    ]
                found = True
                break

        if not found:
            raise ValueError(f"L'automazione '{source}' non è stata trovata.")

        await self.hass.async_add_executor_job(self._write_automations, automations)
        await self.hass.services.async_call("automation", "reload", {}, blocking=True)

    import yaml

    async def mark_done(self, entity_id, name, type_):
        if type_ not in ["sequence", "choice", "order"]:
            return
        if self.orders is None or self.sequences is None or self.choices is None:
            await self.async_initialize()

        if type_ == "order":
            if name not in self.orders:
                raise ValueError(f"L'ordine '{name}' non esiste.")

            order = self.orders[name]

            if entity_id in order.get("done_list", []):
                return

            if entity_id not in order.get("order", []):
                raise ValueError(f"L'automazione '{entity_id}' non è presente nell'ordine '{name}'.")

            order["done"] = order.get("done", 0) + 1
            done_list = order.get("done_list", [])
            done_list.append(entity_id)
            order["done_list"] = done_list

        elif type_ == "sequence":
            if name not in self.sequences:
                raise ValueError(f"La sequenza '{name}' non esiste.")

            data = self.sequences[name]
            sequence = data.get("sequence", [])
            state = data.get("state", {})
            current_step = state.get("step", 0)

            if current_step < len(sequence) and sequence[current_step] == entity_id:
                new_step = min(current_step + 1, len(sequence))
                last_done = sequence[current_step]
                done_flag = new_step == len(sequence)

                data["state"] = {
                    "done": done_flag,
                    "step": new_step,
                    "last": last_done,
                }

        elif type_ == "choice":
            if name not in self.choices:
                raise ValueError(f"La scelta '{name}' non esiste.")

            choice_data = self.choices[name]
            choice_list = choice_data.get("choice", [])

            if entity_id not in choice_list:
                raise ValueError(
                    f"L'automazione '{entity_id}' non è presente nella scelta '{name}'."
                )

            choice_data["state"] = {
                "done": True,
                "selected": entity_id,
            }

        with open(self.EXPRESSIONS_FILE_PATH, "r") as f:
            expressions = yaml.safe_load(f) or {}

        sequences_yaml = []
        for seq_name, seq_data in (self.sequences or {}).items():
            sequences_yaml.append({
                "name": seq_name,
                "sequence": seq_data.get("sequence", []),
                "state": seq_data.get("state", {
                    "done": False,
                    "step": 0,
                    "last": None,
                })
            })

        choices_yaml = []
        for choice_name, choice_data in (self.choices or {}).items():
            choices_yaml.append({
                "name": choice_name,
                "choice": choice_data.get("choice", []),
                "state": choice_data.get("state", {
                    "done": False,
                    "selected": None,
                })
            })

        orders_yaml = []
        for order_name, order_data in self.orders.items():
            orders_yaml.append({
                "name": order_name,
                "order": list(order_data.get("order", [])),
                "total": order_data.get("total", 0),
                "done": order_data.get("done", 0),
                "done_list": list(order_data.get("done_list", [])),
                "state": {
                    "done": order_data.get("done", 0) >= order_data.get("total", 0),
                    "done_list": list(order_data.get("done_list", []))
                }
            })

        expressions["sequences"] = sequences_yaml
        expressions["choices"] = choices_yaml
        expressions["orders"] = orders_yaml

        with open(self.EXPRESSIONS_FILE_PATH, "w") as f:
            yaml.safe_dump(expressions, f)

