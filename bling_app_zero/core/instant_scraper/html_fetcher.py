# (arquivo truncado para foco na alteração principal)

    def _extrair_html_response(self, response: httpx.Response) -> str:
        status = int(getattr(response, "status_code", 0) or 0)
        content_type = str(response.headers.get("content-type", "")).lower()
        texto = response.text or ""

        self._set_last_info(
            url_final=str(getattr(response, "url", "") or ""),
            status_code=str(status),
            content_type=content_type,
            html_chars=len(texto),
        )

        if status >= 400:
            self._set_last_info(motivo=f"http_{status}")
            return ""

        if not texto.strip():
            self._set_last_info(motivo="resposta_vazia")
            return ""

        if "text/html" not in content_type and "<html" not in texto.lower():
            self._set_last_info(motivo="conteudo_nao_html")
            return ""

        # 🔥 CORREÇÃO PRINCIPAL AQUI
        if self._parece_bloqueio(texto):
            # NÃO descarta se HTML for grande (provável falso positivo)
            if len(texto) > 200000:
                self._set_last_info(
                    motivo="possivel_falso_antibot",
                    parece_bloqueio=False,
                )
                return texto[:MAX_HTML_CHARS]

            self._set_last_info(
                motivo="bloqueio_ou_antibot",
                parece_bloqueio=True,
                parece_javascript=self._parece_dependente_js(texto),
            )
            return ""

        if self._parece_dependente_js(texto):
            self._set_last_info(
                motivo="pagina_possivelmente_dependente_de_javascript",
                parece_javascript=True,
            )

        return texto[:MAX_HTML_CHARS]
