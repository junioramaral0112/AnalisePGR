import os
import tempfile
import streamlit as st
from google import genai
from playwright.sync_api import sync_playwright, Error as PlaywrightError
import subprocess

st.set_page_config(page_title="Sistema Automatizado de Contestação e Ajustes de Auditorias SST", layout="wide")

# Sidebar / Config
st.sidebar.title("Configuração")
api_key_sidebar = st.sidebar.text_input("GEMINI_API_KEY", type="password", help="Informe a chave da API Gemini ou configure como Secret no Streamlit Cloud")
st.sidebar.markdown("Versão: 1.0 — Suporte: equipe SST")

api_key = api_key_sidebar.strip() or os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    st.sidebar.error("GEMINI_API_KEY ausente. Configure a variável de ambiente ou informe aqui.")
    client = None
else:
    try:
        genai.api_key = api_key
        client = genai.Client()
        st.sidebar.success("Chave configurada")
    except Exception as e:
        st.sidebar.error(f"Erro ao inicializar cliente GenAI: {e}")
        client = None

st.title("Sistema Automatizado de Contestação e Ajustes de Auditorias SST")

# Form
with st.form("main_form"):
    st.markdown("Envie os PDFs do PGR e PCMSO (empresa) e cole as ressalvas/glosas da auditoria.")
    pgr_file = st.file_uploader("PDF: PGR", type=["pdf"], key="pgr")
    pcmsop_file = st.file_uploader("PDF: PCMSO", type=["pdf"], key="pcmsop")
    ressalvas_text = st.text_area("Ressalvas/Glosas da Auditoria (cole aqui)", height=240)
    submit = st.form_submit_button("Analisar Ressalvas e Gerar Parecer / Documentos")

output_container = st.container()

# Utils
def save_temp_file(uploaded_file):
    t = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    t.write(uploaded_file.read())
    t.flush()
    t.close()
    return t.name

def extract_html_from_text(text: str):
    start_tag = "```html"
    end_tag = "```"
    s = text.find(start_tag)
    if s == -1:
        return None
    s += len(start_tag)
    e = text.find(end_tag, s)
    if e == -1:
        return None
    return text[s:e].strip()

def ensure_playwright_browsers():
    try:
        with sync_playwright() as p:
            return True
    except PlaywrightError:
        try:
            subprocess.check_call(["playwright", "install", "--with-deps"])
            return True
        except Exception:
            return False
    except Exception:
        return False

def html_to_pdf_bytes_playwright(html_code: str):
    ok = ensure_playwright_browsers()
    if not ok:
        raise RuntimeError("Playwright browsers não instalados. No Streamlit Cloud, defina 'playwright install --with-deps' como Install command.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.set_content(html_code, wait_until="networkidle")
        pdf_bytes = page.pdf(format="A4", margin={"top":"10mm","bottom":"10mm","left":"10mm","right":"10mm"})
        browser.close()
        return pdf_bytes

# Main action
if submit:
    if client is None:
        st.error("Cliente GenAI não inicializado. Verifique GEMINI_API_KEY.")
    elif not pgr_file or not pcmsop_file or not ressalvas_text.strip():
        st.error("Por favor, envie os dois PDFs e as ressalvas.")
    else:
        with st.spinner("Preparando arquivos e solicitando análise ao modelo Gemini..."):
            try:
                pgr_path = save_temp_file(pgr_file)
                pcmsop_path = save_temp_file(pcmsop_file)
            except Exception as e:
                st.error(f"Erro salvando PDFs localmente: {e}")
                raise

            # Upload para GenAI
            try:
                resp_pgr = client.files.upload(file=open(pgr_path, "rb"), filename=os.path.basename(pgr_path))
                resp_pcmsop = client.files.upload(file=open(pcmsop_path, "rb"), filename=os.path.basename(pcmsop_path))
            except Exception as e:
                st.error(f"Erro ao enviar arquivos para GenAI: {e}")
                raise

            # Monta prompt sem usar um único triple-quoted f-string (evita erros de terminação)
            prompt_parts = []
            prompt_parts.append("Você é um Médico do Trabalho e Engenheiro de Segurança do Trabalho Sênior. ")
            prompt_parts.ap
