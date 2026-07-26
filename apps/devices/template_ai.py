import json
import logging
from typing import Literal

import google.generativeai as genai
from django.conf import settings
from pydantic import BaseModel, Field, ValidationError

from apps.devices.models import DeviceTemplate

logger = logging.getLogger(__name__)


# Pydantic Schemas for Gemini Structured Response
class RegisterDefinition(BaseModel):
    address: int = Field(
        description="The starting register address (0-based or offset, e.g. 3028). Must be an integer."
    )
    type: Literal["float32", "float", "int64", "int32", "uint16", "int16", "uint32", "int32", "bool"] = Field(
        description="The data type of the register."
    )
    functionCode: Literal[3, 4, 5, 6, 15, 16] = Field(
        description="The Modbus function code (e.g. 3 for Read Holding Registers, 4 for Read Input Registers, etc.)."
    )
    unit: str | None = Field(
        None, description="The unit of measurement, e.g., 'V', 'A', 'W', 'Hz', 'kWh', 'Wh', 'rpm', 'C', 'F'."
    )
    scale: float | None = Field(None, description="The scaling multiplier (if any), e.g., 0.1 or 0.01.")
    writable: bool | None = Field(False, description="Whether the register is writable.")
    control: Literal["input", "toggle", "button"] | None = Field(None, description="Type of UI control if writable.")
    min: float | None = Field(None, description="Minimum allowed value for controls.")
    max: float | None = Field(None, description="Maximum allowed value for controls.")
    labels: list[str] | None = Field(None, description="Labels for toggle or boolean values, e.g. ['Stop', 'Start'].")
    quantity_kind: (
        Literal["power", "energy", "power_factor", "temperature", "runtime", "status", "generation"] | None
    ) = Field(
        None,
        description="Protocol-neutral physical meaning used for verified business-impact calculations.",
    )
    aggregation: Literal["instantaneous", "cumulative_counter", "interval_total", "state", "event"] | None = Field(
        None,
        description="How readings should be aggregated over time.",
    )
    canonical_unit: str | None = Field(None, description="Canonical unit, such as kW, kWh, °C, h, or unitless.")
    conversion_factor: float | None = Field(
        None,
        description="Multiplier converting the reported unit into the canonical unit.",
    )


class AlertPresetDefinition(BaseModel):
    name: str = Field(description="Friendly name for the alert, e.g. 'Low Voltage Warning'.")
    key: str = Field(description="The register key this alert applies to, e.g. 'voltage'.")
    condition: Literal["gt", "lt", "eq", "neq"] = Field(description="Comparison condition: gt, lt, eq, neq.")
    threshold: float = Field(description="Threshold value to trigger the alert.")
    severity: Literal["warning", "critical", "info"] = Field(description="Severity of the alert.")


class DeviceTemplateAIResult(BaseModel):
    name: str = Field(description="Standardized name of the device, e.g. 'Schneider PM5350'.")
    manufacturer: str = Field(description="Standardized manufacturer name, e.g. 'Schneider Electric'.")
    model_number: str = Field(description="Standardized model number, e.g. 'PM5350'.")
    device_type: Literal["power_meter", "solar_inverter", "vfd", "plc", "temp_sensor", "chiller", "other"] = Field(
        description="Categorized device type."
    )
    protocol: Literal["modbus_tcp", "modbus_rtu", "opcua", "mqtt", "bacnet"] = Field(
        description="The communication protocol (typically modbus_tcp or modbus_rtu)."
    )
    category: Literal["energy", "cold_chain", "factory"] = Field(
        description=(
            "Industrial category: energy (Energy Monitoring), cold_chain (Cold Chain), factory (Smart Factory)."
        )
    )
    register_map: dict[str, RegisterDefinition] = Field(
        description=(
            "Key-value mapping of registers. Keys must be snake_case (e.g. voltage, active_power, output_frequency)."
        )
    )
    alert_presets: list[AlertPresetDefinition] = Field(
        default_factory=list, description="Pre-configured list of alert presets based on register keys."
    )
    default_polling_interval: int = Field(5, description="Default polling interval in seconds.")
    source_url: str = Field(description="The exact URL where you found the register map documentation.")
    ai_confidence: float = Field(description="Self-assessed confidence score between 0.0 and 1.0.")


def _build_generation_prompt(
    manufacturer: str,
    model_number: str,
    doc_url: str = None,
    *,
    document_attached: bool = False,
) -> str:
    """Build the Gemini prompt for Modbus register map extraction."""
    prompt = (
        "You are an expert industrial IoT engineering assistant. Your task is to find and extract the "
        f"Modbus register map for the equipment: Manufacturer '{manufacturer}', Model '{model_number}'.\n\n"
    )

    if document_attached:
        prompt += (
            "IMPORTANT: The customer attached an equipment manual. Ground the register map in "
            "that document and do not invent registers that are absent or ambiguous.\n\n"
        )
    elif doc_url:
        prompt += (
            "IMPORTANT: The user has provided a direct documentation URL. Please prioritize and ground "
            f"your search/extraction on this specific page: {doc_url}\n\n"
        )
    else:
        prompt += (
            "Use Google Search to find the manufacturer's official datasheet, Modbus manual, "
            "or register map document.\n\n"
        )

    prompt += (
        "Extract the typical telemetry registers for this equipment. For example:\n"
        "- If it is a power meter: voltage, current, active_power, frequency, energy, "
        "reactive_power, power_factor, etc.\n"
        "- If it is a solar inverter: dc_voltage, dc_current, ac_active_power, status, "
        "total_yield, energy, temp, etc.\n"
        "- If it is a VFD: frequency, output_current, output_power, motor_speed, "
        "speed_setpoint, run_command, status, etc.\n"
        "- If it is a temperature sensor: temperature, humidity, etc.\n\n"
        "Please follow these strict rules:\n"
        "1. Identify the Modbus protocol (usually modbus_tcp or modbus_rtu).\n"
        "2. Identify whether each register is holding register (functionCode 3) or input register (functionCode 4).\n"
        "3. Identify writable registers (functionCode 6 or 16 for holding, 5 for coils) if applicable.\n"
        "4. Assign snake_case names as keys for `register_map` (e.g., 'active_power' or 'dc_voltage').\n"
        "5. Standardize units of measurement (e.g., 'V', 'A', 'W', 'kW', 'Hz', 'kWh', 'Wh', 'rpm', 'C').\n"
        "6. Provide 1-2 standard alert presets in the `alert_presets` field "
        "(e.g., over-temperature, under-voltage) if reasonable.\n"
        "7. Estimate your extraction confidence (0.0 to 1.0) and include the source URL where the map was found. "
        "For an attached manual without a URL, use 'uploaded-equipment-manual' as source_url.\n\n"
        "8. Where the documentation is explicit, provide quantity_kind, aggregation, canonical_unit, and "
        "conversion_factor. Do not guess these fields when the manual is ambiguous.\n\n"
        "Return the output strictly in the requested JSON structure."
    )
    return prompt


def _validate_register_map(register_map: dict) -> tuple[bool, list[str]]:
    """
    Validate that a register map dict is structurally valid.
    Returns (is_valid, list_of_errors)
    """
    errors = []
    if not isinstance(register_map, dict):
        return False, ["Register map must be a dictionary"]

    for key, val in register_map.items():
        # Handle both raw dicts and Pydantic model objects
        if hasattr(val, "model_dump"):
            value = val.model_dump()
        elif hasattr(val, "dict"):
            value = val.dict()
        elif isinstance(val, dict):
            value = val
        else:
            errors.append(f"Register '{key}' must be a dictionary or model instance")
            continue

        # Check required fields
        if "address" not in value:
            errors.append(f"Register '{key}' is missing 'address'")
        elif not isinstance(value["address"], int):
            errors.append(f"Register '{key}' address must be an integer")

        if "type" not in value:
            errors.append(f"Register '{key}' is missing 'type'")

        if "functionCode" not in value:
            errors.append(f"Register '{key}' is missing 'functionCode'")
        elif value.get("functionCode") not in [3, 4, 5, 6, 15, 16]:
            errors.append(f"Register '{key}' functionCode must be one of [3, 4, 5, 6, 15, 16]")

        # Check writable constraints
        if value.get("writable"):
            if "control" not in value:
                errors.append(f"Writable register '{key}' is missing 'control' field")
            elif value.get("control") not in ["input", "toggle", "button"]:
                errors.append(f"Writable register '{key}' control must be 'input', 'toggle', or 'button'")

    return len(errors) == 0, errors


def generate_template_from_ai(
    manufacturer: str,
    model_number: str,
    doc_url: str = None,
    doc_path: str = None,
) -> dict:
    """
    Use Gemini with grounded search to find and parse a Modbus register map.
    Returns a draft template dict (NOT saved to DB yet).
    """
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        logger.error("GEMINI_API_KEY is not configured in settings.")
        return {
            "status": "error",
            "error": "Gemini API key is not configured. Please add GEMINI_API_KEY to your settings/env variables.",
        }

    # Initialize Gemini SDK
    try:
        genai.configure(api_key=api_key)
        # Use gemini-2.0-flash as the search/grounding model
        model = genai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        logger.exception("Failed to configure/initialize Gemini model")
        return {"status": "error", "error": f"Failed to initialize Gemini: {e}"}

    prompt = _build_generation_prompt(
        manufacturer,
        model_number,
        doc_url,
        document_attached=bool(doc_path),
    )

    uploaded_document = None
    try:
        logger.info("Calling Gemini for template generation: %s %s (URL: %s)", manufacturer, model_number, doc_url)

        # Enforce structured output via Pydantic model response_schema
        # Enable search grounding if doc_url is NOT provided (or even if it is, to help find it)
        tools = [] if doc_path else ["google_search"]

        content = prompt
        if doc_path:
            uploaded_document = genai.upload_file(
                path=doc_path,
                mime_type="application/pdf",
                display_name=f"{manufacturer} {model_number} equipment manual",
            )
            content = [uploaded_document, prompt]
        response = model.generate_content(
            content,
            tools=tools,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=DeviceTemplateAIResult,
                temperature=0.1,
            ),
        )

        # Parse the structured response
        response_text = response.text
        logger.debug("Gemini raw response: %s", response_text)

        data = json.loads(response_text)

        # Validate the dict schema using Pydantic model directly to be safe
        result = DeviceTemplateAIResult(**data)

        # Perform custom DB schema validation on register_map
        is_valid, validation_errors = _validate_register_map(result.register_map)
        if not is_valid:
            logger.error("AI-generated register map failed validation: %s", validation_errors)
            return {
                "status": "error",
                "error": f"AI-generated register map failed validation: {', '.join(validation_errors)}",
            }

        return {
            "status": "draft",
            "name": result.name,
            "manufacturer": result.manufacturer,
            "model_number": result.model_number,
            "device_type": result.device_type,
            "protocol": result.protocol,
            "category": result.category,
            "register_map": result.register_map,
            "alert_presets": result.alert_presets,
            "default_polling_interval": result.default_polling_interval,
            "source_url": result.source_url,
            "ai_confidence": result.ai_confidence,
        }

    except ValidationError as ve:
        logger.exception("AI response failed Pydantic validation")
        return {"status": "error", "error": f"AI response did not match template schema: {ve}"}
    except json.JSONDecodeError as je:
        logger.exception("Failed to decode JSON from AI response")
        return {"status": "error", "error": f"AI returned invalid JSON: {je}"}
    except Exception as e:
        logger.exception("AI template generation failed")
        return {"status": "error", "error": f"AI template generation failed: {e}"}
    finally:
        if uploaded_document and getattr(uploaded_document, "name", None):
            try:
                genai.delete_file(uploaded_document.name)
            except Exception:
                logger.warning("Could not remove uploaded AI documentation file")


def save_approved_template(draft: dict, team=None) -> DeviceTemplate:
    """Save a user-approved AI draft as a DeviceTemplate."""
    # Convert Pydantic schemas/dicts if they are still model instances
    register_map = draft.get("register_map")
    if isinstance(register_map, dict):
        # Ensure all nested values are dicts
        serializable_map = {}
        for k, v in register_map.items():
            if hasattr(v, "model_dump"):
                serializable_map[k] = v.model_dump()
            elif isinstance(v, dict):
                serializable_map[k] = v
            else:
                serializable_map[k] = dict(v)
        register_map = serializable_map

    alert_presets = draft.get("alert_presets", [])
    if isinstance(alert_presets, list):
        serializable_alerts = []
        for alert in alert_presets:
            if hasattr(alert, "model_dump"):
                serializable_alerts.append(alert.model_dump())
            elif isinstance(alert, dict):
                serializable_alerts.append(alert)
            else:
                serializable_alerts.append(dict(alert))
        alert_presets = serializable_alerts

    template = DeviceTemplate.objects.create(
        name=draft.get("name"),
        manufacturer=draft.get("manufacturer"),
        model_number=draft.get("model_number"),
        device_type=draft.get("device_type"),
        protocol=draft.get("protocol"),
        category=draft.get("category"),
        register_map=register_map,
        alert_presets=alert_presets,
        default_polling_interval=draft.get("default_polling_interval", 5),
        is_verified=False,
        source="ai_generated",
        source_url=draft.get("source_url", ""),
        ai_confidence=draft.get("ai_confidence"),
        created_by_team=team,
    )
    return template
