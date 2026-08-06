import asyncio
import os
import subprocess
import google.generativeai as genai
import streamlit as st

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Sistema de Contestação e Ajustes de SST",
    page_icon="🛡️",
    layout="wide",
)


# Garante a instalação do Chromium no Playwright
@st.cache_resource
def instalar_playwright_chromium():
    try:
        subprocess.run(
            ["playwright", "install", "chromium"],
            check=True,
            capture_output=True,
        )
    except Exception as e:
        st.error(f"Erro ao instalar o Chromium para o Playwright: {e}")


instalar_playwright_chromium()


# Função assíncrona para gerar PDF via Playwright
async def gerar_pdf_playwright_async(html_code: str) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page()
        await page.set_content(html_code, wait_until="networkidle")

        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "15mm",
                "bottom": "15mm",
                "left": "10mm",
                "right": "10mm",
            },
        )

        await browser.close()
        return pdf_bytes


# Wrapper síncrono para o Streamlit
def gerar_pdf_playwright(html_code: str) -> bytes:
    return asyncio.run(gerar_pdf_playwright_async(html_code))


# Painel Lateral
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de Gestão de Auditoria de SST**\n\n"
    "Análise automatizada de ressalvas de PGR e PCMSO com foco em Riscos Psicossociais (NR-01, NR-07, NR-17)."
)

st.title("🛡️ Análise Automatizada de Auditorias de SST")
st.markdown(
    "Carregue os arquivos do **PGR** e **PCMSO** da empresa e cole o texto das ressalvas/glosas recebidas da auditoria."
)

col1, col2 = st.columns(2)

with col1:
    pgr_file = st.file_uploader(
        "📄 Upload do PGR (PDF):", type=["pdf"], key="pgr"
    )

with col2:
    pcmso_file = st.file_uploader(
        "🩺 Upload do PCMSO (PDF):", type=["pdf"], key="pcmso"
    )

ressalvas_text = st.text_area(
    "📝 Cole o texto das Ressalvas / Glosas da Auditoria aqui:",
    height=180,
    placeholder="Exemplo: O documento foi Aceito com Ressalva pois os riscos psicossociais não constam no Inventário de Riscos Ocupacionais...",
)

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Resposta")

if btn_analisar:
    # 1. Recupera a chave dos Secrets do Streamlit ou do ambiente
    final_api_key = ""
    if "GEMINI_API_KEY" in st.secrets:
        final_api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
    else:
        final_api_key = str(os.environ.get("GEMINI_API_KEY", "")).strip()

    if not final_api_key:
        st.error(
            "⚠️ Nenhuma chave de API configurada! Adicione `GEMINI_API_KEY` nos Secrets do Streamlit Cloud."
        )
    elif not pgr_file or not pcmso_file:
        st.error(
            "⚠️ É obrigatório enviar ambos os arquivos (PGR e PCMSO) para análise!"
        )
    elif not ressalvas_text.strip():
        st.error("⚠️ Digite ou cole o texto das ressalvas recebidas!")
    else:
        with st.spinner(
            "⏳ Processando documentos e executando análise técnica..."
        ):
            try:
                # Configuração Direta e Sem Fallback da API
                genai.configure(api_key=final_api_key)

                # Prepara os PDFs diretamente da memória como partes nativas da API
                pgr_part = {
                    "mime_type": "application/pdf",
                    "data": pgr_file.getvalue(),
                }

                pcmso_part = {
                    "mime_type": "application/pdf",
                    "data": pcmso_file.getvalue(),
                }

                prompt_sistema = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias e Conformidade Normativa de SST (NR-01, NR-07, NR-17, NR-20, NR-35, eSocial).

                Sua missão é analisar as RESSALVAS/GLOSAS emitidas pela auditoria de terceiros e confrontá-las diretamente com os documentos anexados (PGR e PCMSO).

                TEXTO DAS RESSALVAS/GLOSAS DA AUDITORIA:
                {ressalvas_text}

                INSTRUÇÕES DE RESPOSTA:
                1. Analise criticamente se as ressalvas são PROCEDENTES ou IMPROCEDENTES consultando os PDFs enviados.
                2. Gere um PARECER TÉCNICO DE CONTESTAÇÃO E RESPOSTA completo e fundamentado, citando os itens e a legislação vigente (especialmente a transição e regras de Riscos Psicossociais da NR-01 e NR-17).
                3. Se a ressalva exigir a entrega ou reestruturação de um documento, apêndice ou tabela (ex: Inventário de Riscos/Apêndice A), forneça o código HTML5 e CSS3 (inline/style) COMPLETO e formatado para impressão A4 ao final do seu parecer.
                4. SE GERAR CÓDIGO HTML, OBLIGATORIAMENTE coloque o código estritamente entre as tags ```html e ```.
                """

                # Utiliza o modelo gemini-2.5-flash com a SDK nativa e estável
                model = genai.GenerativeModel("gemini-2.5-flash")
                response = model.generate_content(
                    [pgr_part, pcmso_part, prompt_sistema]
                )

                resultado_texto = response.text

                # Exibe a resposta
                st.success("✅ Análise concluída com sucesso!")
                st.markdown("### 📋 Parecer Técnico e Análise de Conformidade")
                st.write(resultado_texto)

                # Se a resposta contiver bloco de código HTML, gera o PDF
                if "```html" in resultado_texto:
                    html_code = (
                        resultado_texto.split("```html")[1]
                        .split("```")[0]
                        .strip()
                    )

                    with st.spinner("📄 Gerando PDF via Chromium Playwright..."):
                        pdf_bytes = gerar_pdf_playwright(html_code)

                    if pdf_bytes:
                        st.markdown("---")
                        st.markdown("### 📥 Documento / Apêndice Gerado")
                        st.download_button(
                            label="📄 Baixar Apêndice/Documento Corrigido em PDF",
                            data=pdf_bytes,
                            file_name="Apendice_Corrigido_SST.pdf",
                            mime="application/pdf",
                        )

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")
