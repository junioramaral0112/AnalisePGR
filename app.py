import asyncio
import os
import re
import subprocess
from openai import OpenAI
from pypdf import PdfReader
import streamlit as st
import streamlit.components.v1 as components

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


# Função assíncrona para gerar PDF via Playwright (A4 Landscape para tabelas largas)
async def gerar_pdf_playwright_async(html_code: str) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page()

        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.set_content(html_code, wait_until="networkidle")

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


# Painel Lateral
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de Gestão de SST & Auditoria**\n\nMotor de IA: **DeepSeek API**"
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
    height=160,
    placeholder="Exemplo: O documento foi Aceito com Ressalva pois os riscos psicossociais não constam no Inventário de Riscos Ocupacionais...",
)

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Parecer / Apêndice")

if btn_analisar:
    # Captura da chave dos Secrets ou Ambiente
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
                texto_pgr = extrair_texto_pdf(pgr_file)
                texto_pcmso = extrair_texto_pdf(pcmso_file)

                client = OpenAI(
                    api_key=api_key, base_url="https://api.deepseek.com"
                )

                prompt_completo = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias e Conformidade Normativa de SST (NR-01, NR-07, NR-17, eSocial).

                Sua missão é emitir o Parecer Técnico de Contestação de SST e a revisão do Apêndice A (Inventário de Riscos).

                --- CONTEÚDO DO PGR ---
                {texto_pgr[:40000]}

                --- CONTEÚDO DO PCMSO ---
                {texto_pcmso[:40000]}

                --- RESSALVAS DA AUDITORIA ---
                {ressalvas_text}

                REGRAS OBRIGATÓRIAS DE FORMATO:
                1. Escreva a resposta INTEIRA dentro de um único documento HTML5 válido, iniciando em <!DOCTYPE html> e fechando em </html>.
                2. Não escreva textos explicativos fora das tags HTML. Toda a resposta (Parecer Técnico + Tabelas do Apêndice A de Riscos Físicos, Químicos, Acidentes, Ergonômicos e Psicossociais) deve estar inclusa no corpo da página HTML.
                3. Utilize estilos CSS modernos inline ou na tag <style> com visual corporativo e profissional (tabelas com bordas limpas, fontes Arial/Helvetica, cabeçalhos destacados).
                4. Retorne o código estritamente delimitado pelas marcas ```html no início e ``` no final.
                """

                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "Você é um gerador automatizado de pareceres de SST formatados em HTML5 completo.",
                        },
                        {"role": "user", "content": prompt_completo},
                    ],
                    stream=False,
                )

                resultado_bruto = response.choices[0].message.content

                # Extrai o código HTML limpo da resposta
                if "```html" in resultado_bruto:
                    codigo_html = (
                        resultado_bruto.split("```html")[1]
                        .split("```")[0]
                        .strip()
                    )
                else:
                    codigo_html = resultado_bruto.strip()

                st.success(
                    "✅ Análise e documento gerados com sucesso pelo DeepSeek!"
                )

                # Área de Downloads (Gera o PDF via Playwright)
                st.markdown("---")
                st.markdown("### 📥 Baixe os Arquivos Gerados")

                col_d1, col_d2 = st.columns(2)

                with col_d2:
                    st.download_button(
                        label="🌐 Baixar Documento Completo em HTML (.html)",
                        data=codigo_html.encode("utf-8"),
                        file_name="Parecer_e_Apendice_SST.html",
                        mime="text/html",
                    )

                with col_d1:
                    with st.spinner("📄 Convertendo documento para PDF..."):
                        pdf_bytes = gerar_pdf_playwright(codigo_html)

                    if pdf_bytes:
                        st.download_button(
                            label="📄 Baixar Parecer e Apêndice em PDF (.pdf)",
                            data=pdf_bytes,
                            file_name="Parecer_e_Apendice_SST.pdf",
                            mime="application/pdf",
                        )

                # Exibe o relatório formatado na tela
                st.markdown("---")
                st.markdown("### 📋 Pré-visualização do Relatório")
                components.html(codigo_html, height=800, scrolling=True)

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")
