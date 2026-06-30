# core/registry.py
"""
Registro genérico de classes/objetos (efeitos, instrumentos, plugins).

Correção vs versão anterior:
- register() sobrescrevia silenciosamente uma chave já existente —
  agora aceita override=False por padrão e avisa via logger se a
  chave já existir, evitando que um plugin sobrescreva outro sem querer.
- Não havia namespacing — dois módulos diferentes registrando "synth"
  colidiam. Agora suporta categorias: register("effects", "compressor", cls).
- get() retornava None silenciosamente se não encontrado — mantido
  (comportamento correto para uso com .get(key, default)), mas adicionado
  get_or_raise() para quando o chamador precisa garantir que existe.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class Registry:
    """
    Registro global categorizado de classes/objetos plugáveis.

    Uso:
        registry = Registry()
        registry.register("effects", "compressor", CompressorEffect)
        registry.register("instruments", "synth", SynthInstrument)

        cls = registry.get("effects", "compressor")
    """

    _instance: Optional["Registry"] = None

    def __new__(cls) -> "Registry":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._data: Dict[str, Dict[str, Any]] = {}
            cls._instance = inst
        return cls._instance

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------

    def register(
        self,
        category: str,
        key: str,
        obj: Any,
        override: bool = False,
    ) -> None:
        """
        Registra um objeto sob uma categoria e chave.

        Se a chave já existir e override=False, loga um aviso e ignora
        (evita que um addon sobrescreva o registro de outro por acidente).
        """
        bucket = self._data.setdefault(category, {})

        if key in bucket and not override:
            from .logger import LOGGER
            LOGGER.warning(
                "Registry",
                f"'{category}/{key}' já registrado — ignorando "
                f"(use override=True para forçar substituição)."
            )
            return

        bucket[key] = obj

    def unregister(self, category: str, key: str) -> bool:
        """Remove um registro. Retorna True se existia."""
        bucket = self._data.get(category, {})
        if key in bucket:
            del bucket[key]
            return True
        return False

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def get(self, category: str, key: str) -> Optional[Any]:
        """Retorna o objeto registrado, ou None se não existir."""
        return self._data.get(category, {}).get(key)

    def get_or_raise(self, category: str, key: str) -> Any:
        """Retorna o objeto registrado, ou levanta KeyError."""
        obj = self.get(category, key)
        if obj is None:
            raise KeyError(f"Nada registrado em '{category}/{key}'.")
        return obj

    def list(self, category: Optional[str] = None) -> List[str]:
        """
        Lista chaves registradas.
        Se category for None, lista as categorias disponíveis.
        Se category for dado, lista as chaves dentro dela.
        """
        if category is None:
            return list(self._data.keys())
        return list(self._data.get(category, {}).keys())

    def clear(self, category: Optional[str] = None) -> None:
        """Limpa uma categoria específica, ou tudo se category for None."""
        if category is None:
            self._data.clear()
        else:
            self._data.pop(category, None)

    def __repr__(self) -> str:
        summary = {cat: len(items) for cat, items in self._data.items()}
        return f"Registry({summary})"


# ------------------------------------------------------------------
# Exemplo de uso:
#
# registry = Registry()
# registry.register("effects", "compressor", CompressorEffect)
# registry.register("instruments", "synth", SynthInstrument)
#
# synth_cls = registry.get("instruments", "synth")
# all_effects = registry.list("effects")
# ------------------------------------------------------------------