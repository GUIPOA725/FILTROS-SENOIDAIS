"""Estruturas de dados da plataforma."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
import json


@dataclass
class Pedido:
    """Dados técnicos/comerciais extraídos do e-mail do cliente."""
    cliente: str = ""
    cnpj: str = ""
    cidade_uf: str = ""
    contato: str = ""
    email_contato: str = ""
    revenda: bool = False
    referencia: str = ""            # nº/assunto da solicitação
    quantidade: int = 1
    topologia: str = "LC"           # LC ou LCL
    tensao_v: float = 440.0         # tensão de linha (rede / saída)
    freq_rede_hz: float = 60.0
    corrente_a: float = 0.0         # corrente nominal do filtro (v1.11: definida pela carga – ver corrente_carga.py)
    corrente_cliente_a: Optional[float] = None   # corrente pedida pelo cliente (informativa, v1.11)
    f_saida_min_hz: float = 0.0
    f_saida_max_hz: float = 60.0
    inversor: str = "GENERICO"
    inversor_corrente_a: float = 0.0
    fs_khz: Optional[float] = None  # freq. de chaveamento (None => padrão do inversor)
    motor_cv: float = 0.0
    motor_kw: float = 0.0
    motor_corrente_a: float = 0.0
    motor_fp: float = 0.85
    motor_rpm: float = 0.0
    motor_polos: int = 4
    fator_servico: float = 1.0
    aplicacao: str = ""
    cabo_m: float = 0.0
    cabo_secao_mm2: float = 0.0     # 0 = dimensiona pela corrente
    cabo_paralelos: int = 0         # 0 = automático
    cabo_blindado: bool = True
    estrela_ao_cc: bool = False     # filtro "all-pole": centro-estrela ligado ao barramento CC do inversor
    vpk_max_v: Optional[float] = None
    dvdt_max_v_us: Optional[float] = None
    rise_time_min_us: Optional[float] = None
    classe_isolamento_kv: float = 1.1
    classe_temp: str = "F (155 °C)"
    elevacao_temp: str = "F (100 K)"
    ip: str = "IP54"
    instalacao: str = "abrigada"
    observacoes: str = ""
    lacunas: List[str] = field(default_factory=list)   # o que não veio no e-mail
    # --- dados de instalação / inversor / motor usados na checagem de dados faltantes (None = não informado) ---
    amb_max_c: Optional[float] = None          # temperatura ambiente máxima no local do painel
    altitude_m: Optional[float] = None
    inversor_controle: str = ""                # escalar V/f | vetorial | DTC
    inversor_filtro_emc: str = ""              # sim/não (capacitores Y internos ligados?)
    aterramento: str = ""                      # TN-S, TN-C, IT, TT
    motor_para_inversor: str = ""              # sim/não (NEMA MG1 Pt.31 / IEC TS 60034-25)
    mancal_isolado: str = ""
    cabo_tipo: str = ""                        # blindado simétrico VFD, unipolar em eletrocalha, etc.
    alim_aux_v: str = ""                       # alimentação dos ventiladores
    dim_max_mm: str = ""                       # espaço disponível L×A×P
    entrada_cabos: str = ""                    # por baixo / por cima
    carga_tipo: str = ""                       # torque quadrático (bomba/ventilador) ou constante
    informados: List[str] = field(default_factory=list)   # campos que vieram de fato no pedido

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Pedido":
        campos = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if "informados" not in campos:
            campos["informados"] = [k for k, v in d.items() if k in cls.__dataclass_fields__ and v not in (None, "", 0, [])
                                    and k not in ("lacunas", "informados")]
        return cls(**campos)

    def salvar(self, caminho: str):
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
