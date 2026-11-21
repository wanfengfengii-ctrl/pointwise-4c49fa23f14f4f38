from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActionCatalog:
    codes: tuple[str, ...]

    def contains(self, code: str) -> bool:
        return code in self.codes


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be nonblank text')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError(f'{field} must contain valid Unicode') from exc
    return value


def build_action_catalog(codes: object) -> ActionCatalog:
    if not isinstance(codes, (list, tuple)):
        raise ValueError('codes must be an array')
    validated = [require_text(code, 'action code') for code in codes]
    if len(set(validated)) != len(validated):
        raise ValueError('duplicate action code')
    return ActionCatalog(tuple(sorted(validated)))
