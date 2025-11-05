# ruff: noqa
from typing import TypedDict


IS_DEBUG = False

AUTOMATION_PATH = "automations.yaml"

TIMESTAMP_MIN_UPDATE = (
    1000  # time limit for retaining failed updates due to an unregistered sensor
)
MAX_LENGTH_CIRCULAR_LIST = 15  # circular queue's length.
MIN_DISTANCE = 4

# custom component
DOMAIN = "eud4xr"

# services
GAME_OBJECT_NAME = "game_object"
SERVICE_SEND_REQUEST = "send_update_to_server_unity"
SERVICE_ADD_SENSOR = "add_sensor"
SERVICE_ADD_VIRTUAL_OBJECT = "add_virtual_object"
SERVICE_UPDATE_FROM_UNITY = "receive_update_from_unity"
SERVICE_ADD_UPDATE_AUTOMATION = "add_update_automation"
SERVICE_REMOVE_AUTOMATION = "remove_automation"
SERVICE_INCREMENT_COUNTER = "increment_counter"

# endpoints
API_GET_AUTOMATIONS = "automations"
API_GET_VIRTUAL_DEVICES = "list_virtual_framed_devices"
API_GET_ECA_CAPABILITIES = "list_eca_capabilities"
API_GET_CONTEXT_OBJECTS = "context_objects"
API_GET_OBJECTS = "objects"
API_GET_VIRTUAL_OBJECTS = "virtual_objects"
API_GET_MULTIMEDIA_FILES = "multimedia_files"
API_GET_CLOSE_OBJECTS = "find_close_objects"
API_EXPRESSION = "expressions"
API_AVAILABLE_ECA_SCRIPTS = "available_eca_scripts"
API_UPDATE_IOTDevice_VISIBILITY_FROM_UNITY = "update_iotdevice_visibility_from_unity"
API_GET_RealObjects_Capabilities = "list_real_objects_capabilities"

# unity services
META_UNITY_SERVER_IP = "http://192.168.1.123:8080" # NOT END WITH '/'
API_UNITY_NOTIFY_UPDATE = "/api/external_updates/"
API_UNITY_NOTIFY_AUTOMATIONS = "/api/automations/"
API_UNITY_NOTIFY_EXPRESSIONS = "/api/expressions/"
API_UNITY_TEST = "/api/test/"

# CONF domain
CONF_SERVER_UNITY_URL = "server_unity_url"
CONF_SERVER_UNITY_TOKEN = "server_unity_token"
CONF_UNITY_ENTITIES = "unity_entities"
# CONF register virtual object
CONF_PAIRS = "pairs"
# CONF eca script
CONF_PLATFORM_ECA_SCRIPT = "eca_script"
CONF_PLATFORM_GAME_OBJECT = "game_object"
CONF_PLATFORM_UNITY_ID = "unity_id"
CONF_PLATFORM_ATTRIBUTES = "attributes"
# CONF update to unity
CONF_SERVICE_UPDATE_FROM_UNITY_SUBJECT = "subject"
CONF_SERVICE_UPDATE_FROM_UNITY_VERB = "verb"
CONF_SERVICE_UPDATE_FROM_UNITY_VARIABLE = "variable_name"
CONF_SERVICE_UPDATE_FROM_UNITY_MODIFIER = "modifier_string"
CONF_SERVICE_UPDATE_FROM_UNITY_PARAMETERS = "parameters"
CONF_SERVICE_UPDATE_FROM_UNITY_VALUE = "value"
# CONF update from unity
CONF_SERVICE_UPDATE_FROM_UNITY_UPDATES = "updates"
CONF_SERVICE_UPDATE_FROM_UNITY_UPDATE = "content"
CONF_SERVICE_UPDATE_FROM_UNITY_TIMESTAMP = "timestamp"
CONF_SERVICE_UPDATE_FROM_UNITY_ATTRIBUTE = "attribute"
CONF_SERVICE_UPDATE_FROM_UNITY_NEW_VALUE = "new_value"
# CONF automation
CONF_SERVICE_ADD_UPDATE_AUTOMATION_DATA = "data"
CONF_SERVICE_REMOVE_AUTOMATION_ID = "automation_id"
# CONF task modelling
CONF_TASK_MODELLING_NAME = "task_modelling"
CONF_TASK_MODELLING_STORE_NAME = "task_modelling"
CONF_TASK_MODELLING_STORE_VERSION = "1"
CONF_TASK_STORE_ORDER_INDEPENDENCE_COUNTERS_KEY = "order_independence_counters"
CONF_TASK_MODELLING_ENTITIES = "task_modelling_entities"
CONF_TASK_MODELLING_EXPRESSIONS = "task_modelling_expressions"

# unuseful attribute/service keys
CONF_UNUSEFUL_KEYS = ["attribution", "restored", "supported_features"]

# condition keys
CONF_JSON_COMPOSITE_KEYS = ["operator", "conditions"]
CONF_JSON_SIMPLE_KEYS = ["component", "property", "symbol", "compareWith"]
CONF_YAML_COMPOSITE_KEYS = ["condition", "conditions"]
CONF_YAML_SIMPLE_KEYS = ["condition", "value_template"]