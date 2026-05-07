"""Núcleo limpo e validado do IA Planilhas Bling.

Regras do Clean Core:
- a planilha modelo manda no sistema;
- cadastro e estoque usam motores independentes;
- o motor só tenta preencher colunas solicitadas pelo modelo;
- se o dado não for encontrado, fica vazio;
- imagens finais usam separador '|';
- GTIN inválido vira vazio;
- CSV final sempre usa ';' e UTF-8-SIG.
"""

CLEAN_CORE_VERSION = "0.2.0"
