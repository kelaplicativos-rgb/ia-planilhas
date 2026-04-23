from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import unicodedata

import pandas as pd
import streamlit as st


LOG_PATH = Path("bling_app_zero/output/debug_log.txt")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

ETAPAS_VALIDAS = ("origem", "precificacao", "mapeamento", "preview_final")


def normalizar_texto(valor: object) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.strip().lower()


def safe_lower(valor: object) -> str:
    return normalizar_texto(valor)


def safe_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def safe_df_dados(df: object) -> bool:
    return safe_df(df)


def safe_df_estrutura(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def obter_df_sessao(*chaves: str) -> pd.DataFrame:
    for chave in chaves:
        valor = st.session_state.get(chave)
        if isinstance(valor, pd.DataFrame):
            return valor
    return pd.DataFrame()


def limpar_chaves_sessao(*chaves: str) -> None:
    for chave in chaves:
        st.session_state.pop(chave, None)


def log_debug(msg: object, nivel: str = "INFO") -> None:
    if "logs_debug" not in st.session_state:
        st.session_state["logs_debug"] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] [{str(nivel).upper()}] {msg}"

    st.session_state["logs_debug"].append(linha)

    try:
        with open(LOG_PATH, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")
    except Exception as exc:
        st.session_state["logs_debug"].append(
            f"[{timestamp}] [ERRO] Falha ao gravar log em arquivo: {exc}"
        )


def obter_logs() -> str:
    try:
        if LOG_PATH.exists():
            return LOG_PATH.read_text(encoding="utf-8")
    except Exception:
        pass

    if "logs_debug" in st.session_state:
        return "\n".join(st.session_state["logs_debug"])

    return ""


def limpar_logs() -> None:
    st.session_state["logs_debug"] = []

    try:
        if LOG_PATH.exists():
            LOG_PATH.unlink()
    except Exception:
        pass


def render_botao_download_logs(
    *,
    key_sufixo: str = "default",
    label: str = "📥 Baixar log debug",
) -> None:
    logs_txt = obter_logs()

    st.download_button(
        label=label,
        data=logs_txt.encode("utf-8") if isinstance(logs_txt, str) else b"",
        file_name="debug_log.txt",
        mime="text/plain",
        use_container_width=True,
        key=f"btn_download_log_debug_{key_sufixo}",
        disabled=not bool(str(logs_txt).strip()),
    )


def render_log_debug(modo: str = "padrao") -> None:
    logs_txt = obter_logs()
    tem_logs = bool(str(logs_txt).strip())

    if modo == "compacto":
        st.markdown("### Log debug")
        col1, col2 = st.columns(2)

        with col1:
            render_botao_download_logs(key_sufixo="compacto", label="📥 Baixar log")

        with col2:
            if st.button(
                "🗑️ Limpar log",
                use_container_width=True,
                key="btn_clear_log_debug_compacto",
                disabled=not tem_logs,
            ):
                limpar_logs()
                st.rerun()

        if tem_logs:
            with st.expander("Ver log", expanded=False):
                st.code(logs_txt, language="text")
        else:
            st.caption("Nenhum log registrado até o momento.")
        return

    st.markdown("---")
    st.markdown("### 🧠 LOG DEBUG")

    if tem_logs:
        with st.expander("Ver log completo", expanded=False):
            st.code(logs_txt, language="text")
    else:
        st.info(
            "Nenhum log disponível ainda. O painel já está ativo e aparecerá preenchido após a primeira execução registrada."
        )

    col1, col2 = st.columns(2)

    with col1:
        render_botao_download_logs(key_sufixo="padrao", label="📥 Baixar log")

    with col2:
        if st.button(
            "🗑️ Limpar log",
            use_container_width=True,
            key="btn_clear_log_debug",
            disabled=not tem_logs,
        ):
            limpar_logs()
            st.rerun()


def _coletar_query_param(nome: str) -> str:
    try:
        valor = st.query_params.get(nome, "")
    except Exception:
        return ""

    if isinstance(valor, list):
        return str(valor[0]).strip() if valor else ""
    return str(valor or "").strip()


def _definir_query_param(nome: str, valor: str) -> None:
    try:
        st.query_params[nome] = valor
    except Exception:
        pass


def get_etapa() -> str:
    etapa = normalizar_texto(st.session_state.get("etapa", "origem"))
    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"
        st.session_state["etapa"] = etapa
    return etapa


def set_etapa(etapa: str) -> str:
    etapa_limpa = normalizar_texto(etapa)
    if etapa_limpa not in ETAPAS_VALIDAS:
        etapa_limpa = "origem"

    st.session_state["etapa"] = etapa_limpa
    _definir_query_param("etapa", etapa_limpa)
    return etapa_limpa


def ir_para_etapa(etapa: str) -> None:
    set_etapa(etapa)


def voltar_para_etapa(etapa: str) -> None:
    set_etapa(etapa)


def sincronizar_etapa_da_url() -> None:
    etapa_url = normalizar_texto(_coletar_query_param("etapa"))
    etapa_state = normalizar_texto(st.session_state.get("etapa", ""))

    if etapa_url in ETAPAS_VALIDAS:
        st.session_state["etapa"] = etapa_url
        return

    if etapa_state in ETAPAS_VALIDAS:
        _definir_query_param("etapa", etapa_state)
        return

    st.session_state["etapa"] = "origem"
    _definir_query_param("etapa", "origem")


def sincronizar_etapa_global(etapa: str | None = None) -> None:
    if etapa:
        set_etapa(etapa)
        return

    sincronizar_etapa_da_url()


def avancar_etapa() -> str:
    etapa_atual = get_etapa()
    ordem = list(ETAPAS_VALIDAS)

    try:
        indice = ordem.index(etapa_atual)
    except ValueError:
        indice = 0

    proxima = ordem[min(indice + 1, len(ordem) - 1)]
    set_etapa(proxima)
    return proxima


def voltar_etapa() -> str:
    etapa_atual = get_etapa()
    ordem = list(ETAPAS_VALIDAS)

    try:
        indice = ordem.index(etapa_atual)
    except ValueError:
        indice = 0

    anterior = ordem[max(indice - 1, 0)]
    set_etapa(anterior)
    return anterior


def voltar_etapa_anterior() -> str:
    return voltar_etapa()


def _label_etapa(etapa: str) -> str:
    mapa = {
        "origem": "➡️ Origem",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "preview_final": "Preview final",
    }
    return mapa.get(etapa, etapa.title())


def render_topo_navegacao() -> None:
    etapa_atual = get_etapa()
    colunas = st.columns(len(ETAPAS_VALIDAS))

    for coluna, etapa in zip(colunas, ETAPAS_VALIDAS):
        with coluna:
            clicou = st.button(
                _label_etapa(etapa),
                use_container_width=True,
                type="primary" if etapa_atual == etapa else "secondary",
                key=f"nav_topo_{etapa}",
            )
            if clicou and etapa != etapa_atual:
                set_etapa(etapa)
                st.rerun()


def normalizar_imagens_pipe(valor: object) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    partes = re.split(r"[|\n\r;,]+", texto)
    urls = []
    vistos = set()

    for parte in partes:
        item = str(parte or "").strip()
        if not item:
            continue
        if item not in vistos:
            vistos.add(item)
            urls.append(item)

    return "|".join(urls)


def _eh_coluna_video(nome_coluna: object) -> bool:
    nome = normalizar_texto(nome_coluna)
    return bool(nome and any(token in nome for token in ["video", "vídeo", "youtube"]))


def zerar_colunas_video(df: pd.DataFrame) -> pd.DataFrame:
    if not safe_df_estrutura(df):
        return pd.DataFrame()

    base = df.copy().fillna("")
    colunas_video = [str(col) for col in base.columns if _eh_coluna_video(col)]

    for coluna in colunas_video:
        base[coluna] = ""

    if colunas_video:
        log_debug(
            f"Colunas de vídeo zeradas automaticamente: {', '.join(colunas_video)}",
            nivel="INFO",
        )

    return base.fillna("")


def _coluna_encontrada(df: pd.DataFrame, candidatos: list[str]) -> str:
    if not safe_df_estrutura(df):
        return ""

    colunas = [str(c) for c in df.columns.tolist()]
    mapa = {normalizar_texto(c): c for c in colunas}

    for candidato in candidatos:
        achado = mapa.get(normalizar_texto(candidato))
        if achado:
            return achado

    return ""


def _colunas_encontradas(df: pd.DataFrame, candidatos: list[str]) -> list[str]:
    if not safe_df_estrutura(df):
        return []

    encontrados: list[str] = []
    colunas = [str(c) for c in df.columns.tolist()]
    mapa = {normalizar_texto(c): c for c in colunas}

    for candidato in candidatos:
        achado = mapa.get(normalizar_texto(candidato))
        if achado and achado not in encontrados:
            encontrados.append(achado)

    return encontrados


def _somente_digitos(valor: object) -> str:
    return re.sub(r"\D+", "", str(valor or "").strip())


def _todos_digitos_iguais(texto: str) -> bool:
    return bool(texto) and len(set(texto)) == 1


def _calcular_digito_gtin(corpo: str) -> int:
    soma = 0
    peso = 3

    for digito in reversed(corpo):
        soma += int(digito) * peso
        peso = 1 if peso == 3 else 3

    return (10 - (soma % 10)) % 10


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin or not gtin.isdigit():
        return False

    if len(gtin) not in {8, 12, 13, 14}:
        return False

    corpo = gtin[:-1]
    digito_informado = int(gtin[-1])
    digito_calculado = _calcular_digito_gtin(corpo)
    return digito_calculado == digito_informado


def _gtin_tem_prefixo_brasil(gtin: str) -> bool:
    if len(gtin) == 13:
        return gtin.startswith(("789", "790"))

    if len(gtin) == 14:
        return gtin[1:4] in {"789", "790"}

    return True


def _gtin_tem_prefixo_gs1_alocado(gtin: str) -> bool:
    if not gtin or len(gtin) not in {13, 14}:
        return True

    prefixo = int(gtin[:3] if len(gtin) == 13 else gtin[1:4])

    faixas_validas = [
        (0, 19), (30, 39), (60, 139), (200, 299), (300, 379),
        (380, 380), (383, 383), (385, 385), (387, 387),
        (400, 440), (450, 459), (460, 469),
        (470, 470), (471, 471), (474, 474), (475, 475),
        (476, 476), (477, 477), (478, 478), (479, 479),
        (480, 480), (481, 481), (482, 482), (484, 484),
        (485, 485), (486, 486), (487, 487), (489, 489),
        (490, 499), (500, 509), (520, 521), (528, 528),
        (529, 529), (530, 530), (531, 531), (535, 535),
        (539, 539), (540, 549), (560, 560), (569, 569),
        (570, 579), (590, 590), (594, 594), (599, 599),
        (600, 601), (603, 603), (608, 608), (609, 609),
        (611, 611), (613, 613), (615, 615), (616, 616),
        (618, 618), (619, 619), (621, 621), (622, 622),
        (624, 624), (625, 625), (626, 626), (627, 627),
        (628, 628), (629, 629), (640, 649),
        (690, 699), (700, 709), (729, 729),
        (730, 739), (740, 740), (741, 741), (742, 742),
        (743, 743), (744, 744), (745, 745), (746, 746),
        (750, 750), (754, 755), (759, 759),
        (760, 769), (770, 771), (773, 773),
        (775, 775), (777, 777), (778, 778), (779, 779),
        (780, 780), (784, 784), (785, 785), (786, 786),
        (789, 790),
        (800, 839), (840, 849), (850, 850),
        (858, 858), (859, 859), (860, 860),
        (865, 865), (867, 867), (868, 869),
        (870, 879), (880, 880), (883, 883),
        (884, 884), (885, 885), (888, 888),
        (890, 890), (893, 893), (896, 896),
        (899, 899), (900, 919), (930, 939),
        (940, 949), (950, 950), (951, 951),
        (955, 955), (958, 958), (977, 979),
    ]

    return any(inicio <= prefixo <= fim for inicio, fim in faixas_validas)


def _gtin_valido(valor: object, aceitar_apenas_prefixo_br: bool = False) -> bool:
    texto = _somente_digitos(valor)

    if not texto:
        return False

    if len(texto) not in {8, 12, 13, 14}:
        return False

    if _todos_digitos_iguais(texto):
        return False

    if not _gtin_checksum_valido(texto):
        return False

    if not _gtin_tem_prefixo_gs1_alocado(texto):
        return False

    if aceitar_apenas_prefixo_br and not _gtin_tem_prefixo_brasil(texto):
        return False

    return True


def _limpar_gtin(valor: object, aceitar_apenas_prefixo_br: bool = False) -> str:
    texto = _somente_digitos(valor)
    if not texto:
        return ""

    if not _gtin_valido(texto, aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br):
        return ""

    return texto


def _serie_texto_limpa(df: pd.DataFrame, coluna: str) -> pd.Series:
    return (
        df[coluna]
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "none": ""})
    )


def _contar_preenchidos(df: pd.DataFrame, coluna: str) -> int:
    if not safe_df_estrutura(df) or not coluna or coluna not in df.columns:
        return 0
    return int(_serie_texto_limpa(df, coluna).ne("").sum())


def _serie_numerica_valida(df: pd.DataFrame, coluna: str) -> pd.Series:
    serie = _serie_texto_limpa(df, coluna)
    serie = (
        serie.str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(serie, errors="coerce")


def _gtin_online_disponivel() -> bool:
    """
    Mantido como ponto de expansão futura.
    Hoje, sem credenciais/integração contratada da GS1, o app usa
    validação local forte e fallback operacional via limpeza.
    """
    return False


def _inicializar_estado_gtin() -> None:
    defaults = {
        "gtin_apenas_prefixo_br": False,
        "gtin_limpar_invalidos": True,
        "gtin_modo_online": False,
        "gtin_ultimo_total_invalidos": 0,
        "gtin_ultimo_total_limpos": 0,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def render_controles_gtin(df_base: pd.DataFrame | None = None) -> None:
    _inicializar_estado_gtin()

    with st.expander("GTIN / EAN", expanded=False):
        st.caption(
            "Validação local forte para GTIN/EAN e GTIN/EAN tributário. "
            "Se a integração online oficial não estiver disponível, você pode limpar os inválidos."
        )

        col1, col2 = st.columns(2)

        with col1:
            somente_br = st.checkbox(
                "Aceitar apenas prefixo BR (789/790)",
                value=bool(st.session_state.get("gtin_apenas_prefixo_br", False)),
                key="gtin_apenas_prefixo_br_widget",
            )
            st.session_state["gtin_apenas_prefixo_br"] = bool(somente_br)

        with col2:
            modo_online = st.checkbox(
                "Tentar validação online oficial",
                value=bool(st.session_state.get("gtin_modo_online", False)),
                key="gtin_modo_online_widget",
                disabled=not _gtin_online_disponivel(),
                help=(
                    "Disponível apenas quando houver integração oficial/contratada configurada."
                    if not _gtin_online_disponivel()
                    else "Usa a integração online oficial configurada."
                ),
            )
            st.session_state["gtin_modo_online"] = bool(modo_online and _gtin_online_disponivel())

        df_referencia = df_base if isinstance(df_base, pd.DataFrame) else obter_df_sessao("df_final", "df_saida", "df_precificado", "df_origem")

        total_invalidos = contar_gtins_invalidos_df(df_referencia)
        st.session_state["gtin_ultimo_total_invalidos"] = int(total_invalidos)

        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            st.metric("GTINs inválidos", int(total_invalidos))

        with c2:
            st.metric("Últimos limpos", int(st.session_state.get("gtin_ultimo_total_limpos", 0)))

        with c3:
            botao_limpar = st.button(
                "🧹 Limpar GTINs inválidos",
                use_container_width=True,
                key="btn_limpar_gtins_invalidos",
                disabled=(not safe_df_estrutura(df_referencia) or int(total_invalidos) == 0),
            )

        if botao_limpar and safe_df_estrutura(df_referencia):
            for chave in ("df_origem", "df_precificado", "df_saida", "df_final"):
                df_sessao = st.session_state.get(chave)
                if isinstance(df_sessao, pd.DataFrame) and safe_df_estrutura(df_sessao):
                    df_limpo, total_limpos = limpar_gtins_invalidos_df(df_sessao)
                    df_limpo = zerar_colunas_video(df_limpo)
                    st.session_state[chave] = df_limpo
                    st.session_state["gtin_ultimo_total_limpos"] = int(total_limpos)

            log_debug(
                f"Botão de limpeza manual de GTINs inválidos acionado. Total limpo: {st.session_state.get('gtin_ultimo_total_limpos', 0)}",
                nivel="INFO",
            )
            st.success(
                f"GTINs inválidos limpos: {st.session_state.get('gtin_ultimo_total_limpos', 0)}"
            )
            st.rerun()


def contar_gtins_invalidos_df(df: pd.DataFrame) -> int:
    if not safe_df_estrutura(df):
        return 0

    aceitar_apenas_prefixo_br = bool(
        st.session_state.get("gtin_apenas_prefixo_br", False)
    )

    colunas_gtin = _colunas_encontradas(
        df,
        [
            "GTIN/EAN",
            "GTIN",
            "EAN",
            "GTIN/EAN tributário",
            "GTIN/EAN Tributário",
            "GTIN tributário",
            "GTIN Tributário",
            "EAN tributário",
            "EAN Tributário",
            "Código de barras",
            "Codigo de barras",
        ],
    )

    total_invalidos = 0

    for coluna_gtin in colunas_gtin:
        serie_gtin = _serie_texto_limpa(df, coluna_gtin)
        gtins_preenchidos = serie_gtin[serie_gtin.ne("")]
        if gtins_preenchidos.empty:
            continue

        invalidos = gtins_preenchidos.apply(
            lambda x: not _gtin_valido(
                x,
                aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
            )
        )
        total_invalidos += int(invalidos.sum())

    return int(total_invalidos)


def limpar_gtins_invalidos_df(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if not safe_df_estrutura(df):
        return pd.DataFrame(), 0

    base = df.copy().fillna("")
    aceitar_apenas_prefixo_br = bool(
        st.session_state.get("gtin_apenas_prefixo_br", False)
    )

    colunas_gtin = _colunas_encontradas(
        base,
        [
            "GTIN/EAN",
            "GTIN",
            "EAN",
            "GTIN/EAN tributário",
            "GTIN/EAN Tributário",
            "GTIN tributário",
            "GTIN Tributário",
            "EAN tributário",
            "EAN Tributário",
            "Código de barras",
            "Codigo de barras",
        ],
    )

    total_limpos = 0

    for coluna_gtin in colunas_gtin:
        serie_original = base[coluna_gtin].astype(str).fillna("")
        serie_limpa = serie_original.apply(
            lambda v: _limpar_gtin(v, aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br)
        )

        removidos = int(
            (
                serie_original.str.strip().replace({"nan": "", "None": "", "none": ""}).ne("")
                & serie_limpa.eq("")
            ).sum()
        )

        total_limpos += removidos
        base[coluna_gtin] = serie_limpa

    base = zerar_colunas_video(base)
    return base.fillna(""), int(total_limpos)


def blindar_df_para_bling(
    df: pd.DataFrame,
    tipo_operacao_bling: str = "cadastro",
    deposito_nome: str = "",
) -> pd.DataFrame:
    if not safe_df_estrutura(df):
        return pd.DataFrame()

    _inicializar_estado_gtin()

    base = df.copy().fillna("")
    operacao = normalizar_texto(tipo_operacao_bling) or "cadastro"
    deposito_nome = str(deposito_nome or "").strip()

    aceitar_apenas_prefixo_br = bool(
        st.session_state.get("gtin_apenas_prefixo_br", False)
    )
    limpar_invalidos = bool(
        st.session_state.get("gtin_limpar_invalidos", True)
    )

    for col in base.columns:
        nome = normalizar_texto(col)

        if "imagem" in nome or nome in {
            "url imagens",
            "url imagem",
            "imagens",
            "imagem",
        }:
            base[col] = base[col].apply(normalizar_imagens_pipe)

    colunas_gtin = _colunas_encontradas(
        base,
        [
            "GTIN/EAN",
            "GTIN",
            "EAN",
            "GTIN/EAN tributário",
            "GTIN/EAN Tributário",
            "GTIN tributário",
            "GTIN Tributário",
            "EAN tributário",
            "EAN Tributário",
            "Código de barras",
            "Codigo de barras",
        ],
    )

    total_limpados = 0

    for coluna_gtin in colunas_gtin:
        serie_original = base[coluna_gtin].astype(str).fillna("")
        novos_valores: list[str] = []

        for valor_original in serie_original.tolist():
            valor_digitos = _somente_digitos(valor_original)

            if not valor_digitos:
                novos_valores.append("")
                continue

            valido = _gtin_valido(
                valor_digitos,
                aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
            )

            if valido:
                novos_valores.append(valor_digitos)
            else:
                if limpar_invalidos:
                    novos_valores.append("")
                    total_limpados += 1
                else:
                    novos_valores.append(valor_digitos)

        base[coluna_gtin] = novos_valores

    st.session_state["gtin_ultimo_total_limpos"] = int(total_limpados)

    if total_limpados > 0:
        log_debug(
            f"GTINs inválidos limpos automaticamente no preview/exportação: {total_limpados}",
            nivel="INFO",
        )

    if operacao == "estoque" and deposito_nome:
        coluna_deposito = _coluna_encontrada(
            base,
            [
                "Depósito (OBRIGATÓRIO)",
                "Depósito",
                "Deposito (OBRIGATÓRIO)",
                "Deposito",
            ],
        )
        if coluna_deposito:
            base[coluna_deposito] = deposito_nome

    base = zerar_colunas_video(base)
    return base.fillna("")


def dataframe_para_csv_bytes(df: pd.DataFrame) -> bytes:
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()

    if isinstance(df, pd.DataFrame) and safe_df_estrutura(df):
        df = zerar_colunas_video(df)

    return df.fillna("").to_csv(index=False).encode("utf-8-sig")


def validar_df_para_download(df: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    erros: list[str] = []

    if not safe_df_estrutura(df):
        return False, ["O DataFrame final não foi gerado."]

    df = zerar_colunas_video(df)

    if len(df.columns) == 0:
        erros.append("A planilha final não possui colunas.")

    operacao = normalizar_texto(tipo_operacao) or "cadastro"

    coluna_codigo = _coluna_encontrada(
        df,
        ["Código", "codigo", "Código do produto", "SKU", "Sku", "sku"],
    )
    if not coluna_codigo:
        erros.append("A planilha final não possui coluna de código reconhecida.")
    else:
        if _contar_preenchidos(df, coluna_codigo) == 0:
            erros.append("Nenhum código foi preenchido na planilha final.")

    if operacao == "cadastro":
        coluna_descricao = _coluna_encontrada(df, ["Descrição", "Descricao"])
        if not coluna_descricao:
            erros.append("A planilha final não possui coluna de descrição reconhecida.")
        else:
            if _contar_preenchidos(df, coluna_descricao) == 0:
                erros.append("Nenhuma descrição foi preenchida na planilha final.")

        coluna_descricao_curta = _coluna_encontrada(df, ["Descrição Curta", "Descricao Curta"])
        if coluna_descricao_curta and _contar_preenchidos(df, coluna_descricao_curta) == 0:
            erros.append("Nenhuma descrição curta foi preenchida na planilha final.")

    coluna_preco = _coluna_encontrada(
        df,
        [
            "Preço de venda",
            "Preço unitário (OBRIGATÓRIO)",
            "Preço unitário",
            "Preço",
            "Valor",
        ],
    )
    if not coluna_preco:
        erros.append("A planilha final não possui coluna de preço reconhecida.")
    else:
        preenchidos_preco = _contar_preenchidos(df, coluna_preco)
        if preenchidos_preco == 0:
            erros.append("Nenhum preço foi preenchido na planilha final.")
        else:
            numeros = _serie_numerica_valida(df, coluna_preco)
            validos = int(numeros.notna().sum())
            positivos = int((numeros.fillna(0) > 0).sum())

            if validos == 0:
                erros.append("Os preços da planilha final não estão em formato numérico válido.")
            elif positivos == 0:
                erros.append("Nenhum preço positivo foi encontrado na planilha final.")

    if operacao == "estoque":
        coluna_deposito = _coluna_encontrada(
            df,
            [
                "Depósito (OBRIGATÓRIO)",
                "Depósito",
                "Deposito (OBRIGATÓRIO)",
                "Deposito",
            ],
        )
        if not coluna_deposito:
            erros.append("A planilha final não possui coluna de depósito reconhecida.")
        else:
            if _contar_preenchidos(df, coluna_deposito) == 0:
                erros.append("Nenhum depósito foi preenchido na planilha final.")

    aceitar_apenas_prefixo_br = bool(
        st.session_state.get("gtin_apenas_prefixo_br", False)
    )

    colunas_gtin = _colunas_encontradas(
        df,
        [
            "GTIN/EAN",
            "GTIN",
            "EAN",
            "GTIN/EAN tributário",
            "GTIN/EAN Tributário",
            "GTIN tributário",
            "GTIN Tributário",
            "EAN tributário",
            "EAN Tributário",
            "Código de barras",
            "Codigo de barras",
        ],
    )

    for coluna_gtin in colunas_gtin:
        serie_gtin = _serie_texto_limpa(df, coluna_gtin)
        gtins_preenchidos = serie_gtin[serie_gtin.ne("")]
        if gtins_preenchidos.empty:
            continue

        invalidos = gtins_preenchidos.apply(
            lambda x: not _gtin_valido(
                x,
                aceitar_apenas_prefixo_br=aceitar_apenas_prefixo_br,
            )
        )
        if bool(invalidos.any()):
            erros.append(
                f"Existem GTINs preenchidos inválidos na coluna '{coluna_gtin}'."
            )

    return len(erros) == 0, erros
