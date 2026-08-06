import asyncio
import os
import subprocess
import tempfile
from google import genai
from google.genai import types
import streamlit as st

# ==============================================================================
# CONFIGURAÇÃO DA CHAVE DA API FIXA NO CÓDIGO
# Insira sua chave Gemini dentro das aspas abaixo:
API_KEY_FIXA = "AQ.Ab8RN6LVrpAvsn2WJaHvlt1Tr66kIBI34maBbQ93dpCBmurKFA"
# ==============================================================================

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Sistema de Contestação e Ajustes de SST",
    page_icon="🛡️",
    layout="wide",
)


# Garante que o Chromium do Playwright esteja instalado
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


def gerar_pdf_playwright(html_code: str) -> bytes:
    return asyncio.run(gerar_pdf_playwright_async(html_code))


# Título Principal
st.title("🛡️ Análise Automatizada de Auditorias de SST")
st.markdown(
    "Carregue os arquivos do **PGR** e **PCMSO** da empresa e cole o texto das ressalvas/glosas recebidas da auditoria."
)

# Formulário de entrada de dados
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

# Processamento da análise
if btn_analisar:
    # Determina a chave (prioriza a chave fixa ou o segredo do ambiente)
    final_api_key = API_KEY_FIXA or os.environ.get("GEMINI_API_KEY", "")

    if not final_api_key or final_api_key == "SUA_CHAVE_GEMINI_AQUI":
        st.error(
            "⚠️ Por favor, cole sua GEMINI_API_KEY na variável `API_KEY_FIXA` no topo do arquivo `app.py`!"
        )
    elif not pgr_file or not pcmso_file:
        st.error(
            "⚠️ É obrigatório enviar ambos os arquivos (PGR e PCMSO) para análise!"
        )
    elif not ressalvas_text.strip():
        st.error("⚠️ Digite ou cole o texto das ressalvas recebidas!")
    else:
        with st.spinner(
            "⏳ Enviando documentos para a IA e processando análise técnica..."
        ):
            try:
                client = genai.Client(api_key=final_api_key)

                # Cria arquivos temporários
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp_pgr:
                    tmp_pgr.write(pgr_file.getbuffer())
                    pgr_path = tmp_pgr.name

                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".pdf"
                ) as tmp_pcmso:
                    tmp_pcmso.write(pcmso_file.getbuffer())
                    pcmso_path = tmp_pcmso.name

                # Upload dos PDFs para a API
                up_pgr = client.files.upload(file=pgr_path)
                up_pcmso = client.files.upload(file=pcmso_path)

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

                # ALTERADO PARA gemini-2.5-flash PARA EVITAR ERRO DE COTA/429
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[up_pgr, up_pcmso, prompt_sistema],
                )

                resultado_texto = response.text

                # Exibe o parecer técnico na tela
                st.success("✅ Análise concluída com sucesso!")
                st.markdown("### 📋 Parecer Técnico e Análise de Conformidade")
                st.write(resultado_texto)

                # Se houver HTML na resposta, gera o PDF
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

                # Limpeza de arquivos temporários
                os.remove(pgr_path)
                os.remove(pcmso_path)
                client.files.delete(name=up_pgr.name)
                client.files.delete(name=up_pcmso.name)

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")
