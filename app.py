import asyncio
import os
import subprocess
from openai import OpenAI
from pypdf import PdfReader
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
        st.error(f"Erro ao instalar o Chromium: {e}")


instalar_playwright_chromium()


# Função para extrair texto de PDF em memória
def extrair_texto_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        texto = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texto += t + "\n"
        return texto
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return ""


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


# Interface
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de Gestão de Auditoria de SST**\n\nMotor de IA: **DeepSeek API**"
)

st.title("🛡️ Análise Automatizada de Auditorias de SST (DeepSeek)")
st.markdown(
    "Carregue os arquivos do **PGR** e **PCMSO** da empresa e cole o texto das ressalvas/glosas recebidas."
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

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Resposta com DeepSeek")

if btn_analisar:
    # 1. Busca a chave do DeepSeek dos Secrets ou Ambiente
    api_key = ""
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = str(st.secrets["DEEPSEEK_API_KEY"]).strip()
    else:
        api_key = str(os.environ.get("DEEPSEEK_API_KEY", "")).strip()

    if not api_key:
        st.error(
            "⚠️ Nenhuma chave do DeepSeek configurada! Adicione `DEEPSEEK_API_KEY` nos Secrets do Streamlit Cloud."
        )
    elif not pgr_file or not pcmso_file:
        st.error("⚠️ É obrigatório enviar ambos os arquivos (PGR e PCMSO)!")
    elif not ressalvas_text.strip():
        st.error("⚠️ Digite ou cole o texto das ressalvas recebidas!")
    else:
        with st.spinner(
            "⏳ Lendo documentos e enviando para a API do DeepSeek..."
        ):
            try:
                # Extrai os textos dos PDFs
                texto_pgr = extrair_texto_pdf(pgr_file)
                texto_pcmso = extrair_texto_pdf(pcmso_file)

                # Inicializa o cliente apontando para o servidor do DeepSeek
                client = OpenAI(
                    api_key=api_key, base_url="https://api.deepseek.com"
                )

                prompt_completo = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias e Conformidade Normativa de SST (NR-01, NR-07, NR-17, NR-20, NR-35, eSocial).

                Sua missão é analisar as RESSALVAS/GLOSAS emitidas pela auditoria de terceiros e confrontá-las diretamente com o texto do PGR e PCMSO fornecidos abaixo.

                --- CONTEÚDO EXTRAÍDO DO PGR ---
                {texto_pgr[:40000]}

                --- CONTEÚDO EXTRAÍDO DO PCMSO ---
                {texto_pcmso[:40000]}

                --- TEXTO DAS RESSALVAS/GLOSAS DA AUDITORIA ---
                {ressalvas_text}

                INSTRUÇÕES DE RESPOSTA:
                1. Analise criticamente se as ressalvas são PROCEDENTES ou IMPROCEDENTES consultando os textos do PGR e PCMSO.
                2. Gere um PARECER TÉCNICO DE CONTESTAÇÃO E RESPOSTA completo e fundamentado, citando os itens e a legislação vigente (especialmente a transição e regras de Riscos Psicossociais da NR-01 e NR-17).
                3. Se a ressalva exigir a entrega ou reestruturação de um documento, apêndice ou tabela (ex: Inventário de Riscos/Apêndice A), forneça o código HTML5 e CSS3 (inline/style) COMPLETO e formatado para impressão A4 ao final do seu parecer.
                4. SE GERAR CÓDIGO HTML, OBLIGATORIAMENTE coloque o código estritamente entre as tags ```html e ```.
                """

                # Faz a chamada para a API do DeepSeek
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "Você é um especialista em auditorias e normas de Segurança e Saúde no Trabalho (SST).",
                        },
                        {"role": "user", "content": prompt_completo},
                    ],
                    stream=False,
                )

                resultado_texto = response.choices[0].message.content

                st.success("✅ Análise concluída com sucesso via DeepSeek!")
                st.markdown("### 📋 Parecer Técnico e Análise de Conformidade")
                st.write(resultado_texto)

                # Processamento do PDF via Playwright caso a IA tenha retornado HTML
                if "```html" in resultado_texto:
                    html_code = (
                        resultado_texto.split("```html")[1]
                        .split("```")[0]
                        .strip()
                    )

                    with st.spinner(
                        "📄 Gerando PDF formatado via Chromium..."
                    ):
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
                st.error(f"❌ Ocorreu um erro no DeepSeek: {str(e)}")
