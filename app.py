import asyncio
import os
import re
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


# Função para extrair texto dos PDFs
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


# Função assíncrona para gerar PDF via Playwright (A4 Paisagem/Landscape se for tabela larga)
async def gerar_pdf_playwright_async(html_code: str) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page()

        # Define viewport grande para renderizar tabelas largas sem corte
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.set_content(html_code, wait_until="networkidle")

        # Gera PDF no formato A4 em orientação Paisagem (Landscape) para caber todas as colunas do Apêndice
        pdf_bytes = await page.pdf(
            format="A4",
            landscape=True,
            print_background=True,
            margin={
                "top": "10mm",
                "bottom": "10mm",
                "left": "10mm",
                "right": "10mm",
            },
        )

        await browser.close()
        return pdf_bytes


def gerar_pdf_playwright(html_code: str) -> bytes:
    return asyncio.run(gerar_pdf_playwright_async(html_code))


# Interface do Streamlit
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de SST & Auditoria**\n\nGerador de Contestações e Apêndices Normativos via **DeepSeek API**."
)

st.title("🛡️ Análise Automatizada de Auditorias de SST")
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
    height=160,
    placeholder="Exemplo: O documento foi Aceito com Ressalva pois os riscos psicossociais não constam no Inventário de Riscos Ocupacionais...",
)

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Parecer / Apêndice")

if btn_analisar:
    # Captura da Chave de API dos Secrets ou Variável de Ambiente
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
            "⏳ Lendo documentos e processando análise técnica com o DeepSeek..."
        ):
            try:
                # Extrai conteúdo dos arquivos enviados
                texto_pgr = extrair_texto_pdf(pgr_file)
                texto_pcmso = extrair_texto_pdf(pcmso_file)

                client = OpenAI(
                    api_key=api_key, base_url="https://api.deepseek.com"
                )

                prompt_completo = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias e Conformidade Normativa de SST (NR-01, NR-07, NR-17, eSocial).

                Sua missão é analisar as RESSALVAS/GLOSAS emitidas pela auditoria de terceiros e confrontá-las com os documentos anexados (PGR e PCMSO).

                --- CONTEÚDO DO PGR ---
                {texto_pgr[:40000]}

                --- CONTEÚDO DO PCMSO ---
                {texto_pcmso[:40000]}

                --- RESSALVAS DA AUDITORIA ---
                {ressalvas_text}

                DIRETRIZES DE SAÍDA:
                1. Emita o PARECER TÉCNICO DE CONTESTAÇÃO E RESPOSTA completo fundamentado na legislação.
                2. Se for necessário emitir um Apêndice/Inventário de Riscos corrigido, inclua obrigatoriamente a tabela completa com TODOS os riscos (Físicos, Químicos, Acidentes, Ergonômicos e Psicossociais).
                3. OBRIGATÓRIO: Forneça o código HTML5/CSS3 COMPLETO (com as tags <!DOCTYPE html><html>...</html>) contendo toda a estrutura visual e os DADOS PREENCHIDOS DAS TABELAS.
                4. Coloque o código HTML estritamente envolvido pelas marcas: ```html e ```.
                """

                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "Você é um especialista em auditorias e normas de Segurança do Trabalho.",
                        },
                        {"role": "user", "content": prompt_completo},
                    ],
                    stream=False,
                )

                resultado_texto = response.choices[0].message.content

                st.success("✅ Análise concluída com sucesso!")
                st.markdown("### 📋 Parecer Técnico de SST")
                st.write(resultado_texto)

                # Busca o bloco HTML na resposta com Expressão Regular robusta
                match = re.search(
                    r"```html\s*(.*?)\s*```", resultado_texto, re.DOTALL
                )

                if match:
                    codigo_html = match.group(1).strip()

                    st.markdown("---")
                    st.markdown("### 📥 Arquivos do Apêndice Gerados")

                    c_down1, c_down2 = st.columns(2)

                    # Botão 1: Baixar em HTML direto (para abrir no navegador ou Word)
                    with c_down1:
                        st.download_button(
                            label="🌐 Baixar Apêndice em HTML (.html)",
                            data=codigo_html.encode("utf-8"),
                            file_name="Apendice_Corrigido_SST.html",
                            mime="text/html",
                        )

                    # Botão 2: Converter e Baixar em PDF (A4 Landscape) via Playwright
                    with c_down2:
                        with st.spinner("📄 Convertendo HTML em PDF..."):
                            pdf_bytes = gerar_pdf_playwright(codigo_html)

                        if pdf_bytes:
                            st.download_button(
                                label="📄 Baixar Apêndice em PDF (.pdf)",
                                data=pdf_bytes,
                                file_name="Apendice_Corrigido_SST.pdf",
                                mime="application/pdf",
                            )

            except Exception as e:
                st.error(f"❌ Ocorreu um erro no processamento: {str(e)}")
