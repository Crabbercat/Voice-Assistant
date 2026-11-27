import json
from pathlib import Path
from typing import Any

from app.ai.command.normalizer import normalize_text
from app.devices.registry import DeviceRegistry, device_registry


class CatalogueConfigurationError(ValueError):
    """Raised when the command catalogue cannot be used safely."""


class RapidFuzzUnavailableError(RuntimeError):
    """Raised when the optional RapidFuzz dependency is missing."""


class CommandProcessor:
    _ACTION_WORDS = {
        "turn_on": {"bat", "mo"},
        "turn_off": {"tat", "ngat"},
    }
    _NEGATION_WORDS = {"khong", "dung", "chua", "khoi"}

    def __init__(
        self,
        catalogue_path: Path | None = None,
        registry: DeviceRegistry = device_registry,
        similarity_threshold: float = 80,
    ) -> None:
        self.catalogue_path = catalogue_path or (
            Path(__file__).resolve().parents[4]
            / "hardware"
            / "configs"
            / "commands.json"
        )
        self.registry = registry
        self.similarity_threshold = similarity_threshold
        self.catalogue = self._load_catalogue()

    def _load_catalogue(self) -> dict[str, Any]:
        try:
            data = json.loads(self.catalogue_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CatalogueConfigurationError(
                f"Cannot load command catalogue: {self.catalogue_path}: {error}"
            ) from error

        if (
            not isinstance(data, dict)
            or type(data.get("version")) is not int
            or data["version"] != 1
        ):
            raise CatalogueConfigurationError("Unsupported command catalogue version.")
        if not isinstance(data.get("commands"), list):
            raise CatalogueConfigurationError("Catalogue 'commands' must be a list.")
        if not isinstance(data.get("device_types"), dict):
            raise CatalogueConfigurationError("Catalogue 'device_types' must be an object.")
        if not isinstance(data.get("targets"), dict):
            raise CatalogueConfigurationError("Catalogue 'targets' must be an object.")

        command_ids: set[str] = set()
        aliases: dict[str, tuple[str, str]] = {}
        for command in data["commands"]:
            if not isinstance(command, dict):
                raise CatalogueConfigurationError("Each command must be an object.")
            required = ("id", "intent", "action", "device_type", "aliases")
            if any(not command.get(field) for field in required):
                raise CatalogueConfigurationError(
                    "Each command requires id, intent, action, device_type, and aliases."
                )
            if any(
                not isinstance(command[field], str)
                for field in ("id", "intent", "action", "device_type")
            ):
                raise CatalogueConfigurationError(
                    "Command id, intent, action, and device_type must be text."
                )
            command_id = command["id"]
            if command_id in command_ids:
                raise CatalogueConfigurationError(f"Duplicate command id: {command_id}")
            command_ids.add(command_id)
            if command["action"] not in self._ACTION_WORDS:
                raise CatalogueConfigurationError(
                    f"Unsupported action in command {command_id}: {command['action']}"
                )
            if command["device_type"] not in data["device_types"]:
                raise CatalogueConfigurationError(
                    f"Unknown device type in command {command_id}: "
                    f"{command['device_type']}"
                )
            if not isinstance(command["aliases"], list) or not command["aliases"]:
                raise CatalogueConfigurationError(
                    f"Command {command_id} must have at least one alias."
                )

            if type(command.get("enabled", True)) is not bool:
                raise CatalogueConfigurationError(
                    f"Command {command_id} has an invalid enabled value."
                )
            for alias in command["aliases"]:
                if not isinstance(alias, str):
                    raise CatalogueConfigurationError(
                        f"Command {command_id} has a non-text alias."
                    )
                normalized_alias = normalize_text(alias)
                if not normalized_alias:
                    raise CatalogueConfigurationError(
                        f"Command {command_id} has an empty alias."
                    )
                mapping = (command["intent"], command["action"])
                previous = aliases.get(normalized_alias)
                if previous is not None and previous != mapping:
                    raise CatalogueConfigurationError(
                        f"Conflicting command alias: {normalized_alias}"
                    )
                aliases[normalized_alias] = mapping

        for section in ("device_types", "targets"):
            for key, values in data[section].items():
                if not isinstance(values, list) or not values:
                    raise CatalogueConfigurationError(
                        f"Catalogue {section}.{key} must contain aliases."
                    )
                if any(not isinstance(value, str) or not normalize_text(value) for value in values):
                    raise CatalogueConfigurationError(
                        f"Catalogue {section}.{key} has an empty alias."
                    )
        return data

    @staticmethod
    def _contains_phrase(tokens: list[str], phrase: str) -> bool:
        phrase_tokens = phrase.split()
        return any(
            tokens[index : index + len(phrase_tokens)] == phrase_tokens
            for index in range(len(tokens) - len(phrase_tokens) + 1)
        )

    def _detected_keys(self, tokens: list[str], section: str) -> list[str]:
        return [
            key
            for key, aliases in self.catalogue[section].items()
            if any(
                self._contains_phrase(tokens, normalize_text(alias))
                for alias in aliases
            )
        ]

    def _device_type(self, device: Any) -> str | None:
        name_tokens = normalize_text(device.name).split()
        matches = self._detected_keys(name_tokens, "device_types")
        return matches[0] if len(matches) == 1 else None

    def _resolve_device(
        self,
        device_type: str,
        target: str | None,
    ) -> tuple[Any | None, str | None, str | None]:
        candidates = [
            device
            for device in self.registry.get_all()
            if self._device_type(device) == device_type
        ]

        if target is not None:
            target_aliases = {
                normalize_text(alias)
                for alias in self.catalogue["targets"][target]
            }
            candidates = [
                device
                for device in candidates
                if normalize_text(device.room) in target_aliases
            ]
            if not candidates:
                return None, target, "TARGET_NOT_FOUND"
            if len(candidates) > 1:
                return None, target, "AMBIGUOUS_TARGET"
            return candidates[0], target, None

        if len(candidates) > 1:
            return None, None, "AMBIGUOUS_TARGET"
        if not candidates:
            return None, None, "TARGET_NOT_FOUND"

        device = candidates[0]
        room = normalize_text(device.room)
        resolved_target = next(
            (
                key
                for key, aliases in self.catalogue["targets"].items()
                if room in {normalize_text(alias) for alias in aliases}
            ),
            None,
        )
        return device, resolved_target, None

    @staticmethod
    def _result(
        text: str,
        normalized: str,
        threshold: float,
        reason: str,
        *,
        command: dict[str, Any] | None = None,
        target: str | None = None,
        device_id: str | None = None,
        score: float | None = None,
    ) -> dict[str, Any]:
        return {
            "accepted": reason == "MATCH_ACCEPTED",
            "reason": reason,
            "recognized_text": text,
            "normalized_text": normalized,
            "command_id": command.get("id") if command else None,
            "intent": command.get("intent") if command else None,
            "action": command.get("action") if command else None,
            "device_type": command.get("device_type") if command else None,
            "target": target,
            "device_id": device_id,
            "confidence": score,
            "threshold": threshold,
        }

    def process(self, text: str) -> dict[str, Any]:
        normalized = normalize_text(text)
        threshold = self.similarity_threshold
        if not normalized:
            return self._result(text, normalized, threshold, "EMPTY_TRANSCRIPT")

        tokens = normalized.split()
        if self._NEGATION_WORDS.intersection(tokens):
            return self._result(text, normalized, threshold, "NEGATION_DETECTED")

        actions = [
            action
            for action, words in self._ACTION_WORDS.items()
            if words.intersection(tokens)
        ]
        if len(actions) > 1:
            reason = (
                "AMBIGUOUS_COMMAND"
                if "hay" in tokens or "hoac" in tokens
                else "CONFLICTING_ACTION"
            )
            return self._result(text, normalized, threshold, reason)
        if not actions:
            return self._result(text, normalized, threshold, "NO_MATCH")

        device_types = self._detected_keys(tokens, "device_types")
        if len(device_types) > 1:
            return self._result(text, normalized, threshold, "AMBIGUOUS_COMMAND")
        if not device_types:
            return self._result(text, normalized, threshold, "NO_MATCH")

        action = actions[0]
        device_type = device_types[0]
        candidates = [
            command
            for command in self.catalogue["commands"]
            if command.get("enabled", True)
            and command["action"] == action
            and command["device_type"] == device_type
        ]
        if not candidates:
            return self._result(text, normalized, threshold, "NO_MATCH")

        try:
            from rapidfuzz import fuzz
        except ImportError as error:
            raise RapidFuzzUnavailableError(
                "Install AI dependencies with "
                "'pip install -r backend/requirements/ai.txt'."
            ) from error

        ranked = sorted(
            (
                (
                    max(
                        fuzz.token_set_ratio(normalized, normalize_text(alias))
                        for alias in command["aliases"]
                    ),
                    command,
                )
                for command in candidates
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        score, command = ranked[0]

        if len(ranked) > 1 and score - ranked[1][0] <= 3:
            competing = ranked[1][1]
            if (command["intent"], command["action"]) != (
                competing["intent"],
                competing["action"],
            ):
                return self._result(
                    text,
                    normalized,
                    threshold,
                    "AMBIGUOUS_COMMAND",
                    score=round(score, 1),
                )

        if score < threshold:
            return self._result(
                text,
                normalized,
                threshold,
                "BELOW_THRESHOLD",
                command=command,
                score=round(score, 1),
            )

        targets = self._detected_keys(tokens, "targets")
        if len(targets) > 1:
            return self._result(
                text,
                normalized,
                threshold,
                "AMBIGUOUS_TARGET",
                command=command,
                score=round(score, 1),
            )
        target = targets[0] if targets else None
        target_markers = {"phong", "lau", "tang", "san", "bep", "vuon"}
        if target is None and target_markers.intersection(tokens):
            return self._result(
                text,
                normalized,
                threshold,
                "TARGET_NOT_FOUND",
                command=command,
                score=round(score, 1),
            )

        device, resolved_target, target_error = self._resolve_device(
            device_type,
            target,
        )
        if target_error:
            return self._result(
                text,
                normalized,
                threshold,
                target_error,
                command=command,
                target=resolved_target,
                score=round(score, 1),
            )

        return self._result(
            text,
            normalized,
            threshold,
            "MATCH_ACCEPTED",
            command=command,
            target=resolved_target,
            device_id=device.device_id,
            score=round(score, 1),
        )
