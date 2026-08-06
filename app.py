import os
import io
import tempfile
import streamlit as st
from google import genai
from weasyprint import HTML

# ---------- Configurações ----------
st.set_page_config(page_title="Sistema Automatizado de Contestação e Ajustes de Auditorias SST", layout="wide")

st.sidebar.title("Configuração")
api_key_sidebar = st.sidebar.text_input("GEMINI_API_KEY", type="password", help="Informe a chave da API Gemini ou deixe vazio para usar GEMINI_API_KEY do ambiente")
api_key = api_key_sidebar.strip() or os.environ.get("GEMINI_API_KEY", "")
version_info = "v1.0 — Suporte: equipe SST"
st.sidebar.info(version_info)

if not api_key:
    st.sidebar.error("Chave GEMINI_API_KEY ausente. Informe na sidebar ou defina variável de ambiente.")
else:
    # tentativa rápida de inicializar client
    try:
        genai.api_key = api_key
        client = genai.Client()  # usa GENAI API key definida acima
        st.sidebar.success("Chave configurada")
    except Exception as e:
        st.sidebar.error(f"Falha ao inicializar client: {e}")
        client = None

st.title("Sistema Automatizado de Contestação e Ajustes de Auditorias SST")

with st.form("main_form"):
    st.markdown("Envie os PDFs do PGR e PCMSO (empresa) e cole as ressalvas/glosas da auditoria.")
    pgr_file = st.file_uploader("PDF: PGR", type=["pdf"], key="pgr")
    pcmsop_file = st.file_uploader("PDF: PCMSO", type=["pdf"], key="pcmsop")
    ressalvas_text = st.text_area("Ressalvas/Glosas da Auditoria (cole aqui)", height=240)
    submit = st.form_submit_button("Analisar Ressalvas e Gerar Parecer / Documentos")

output_container = st.container()

# Funções utilitárias
def save_temp_file(uploaded_file):
    suffix = ".pdf"
    t = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    t.write(uploaded_file.read())
    t.flush()
    t.close()
    return t.name

def upload_to_genai(client, path, filename):
    # client.files.upload(file=...) interface
    with open(path, "rb") as f:
        try:
            resp = client.files.upload(file=f, filename=filename)
            file_id = getattr(resp, "name", None) or resp.get("name") if isinstance(resp, dict) else None
            # Some SDK variants return id in resp["id"] or resp.name; we try multiple
            if not file_id:
                file_id = resp.get("id") if isinstance(resp, dict) else None
            return resp
        except Exception as e:
            raise

def extract_html_from_text(text):
    # procura trecho entre ```html ... ```
    start_tag = "```html"
    end_tag = "```"
    start = text.find(start_tag)
    if start == -1:
        return None
    start += len(start_tag)
    end = text.find(end_tag, start)
    if end == -1:
        return None
    return text[start:end].strip()

if submit:
    if not client:
        st.error("Cliente da API não inicializado. Verifique a chave.")
    elif not pgr_file or not pcmsop_file or not ressalvas_text.strip():
        st.error("Por favor, envie os dois PDFs e as ressalvas.")
    else:
        with st.spinner("Preparando arquivos e solicitando análise ao modelo Gemini..."):
            # Salvar temporariamente
            try:
                pgr_path = save_temp_file(pgr_file)
                pcmsop_path = save_temp_file(pcmsop_file)
            except Exception as e:
                st.error(f"Erro salvando PDFs localmente: {e}")
                raise

            # Upload para GenAI (temporário) - tratamento simples
            uploaded = {}
            try:
                resp_pgr = client.files.upload(file=open(pgr_path, "rb"), filename=os.path.basename(pgr_path))
                resp_pcmsop = client.files.upload(file=open(pcmsop_path, "rb"), filename=os.path.basename(pcmsop_path))
                uploaded["pgr"] = resp_pgr
                uploaded["pcmsop"] = resp_pcmsop
            except Exception as e:
                st.error(f"Erro ao enviar arquivos para GenAI: {e}")
                raise

            # Construir prompt instruindo o modelo conforme especificado
            prompt = f"""
Você é um Médico do Trabalho e Engenheiro de Segurança do Trabalho Sênior. Analise criticamente as ressalvas abaixo, confrontando-as com as Normas Regulamentadoras NR-01, NR-07, NR-17, NR-20 e NR-35, e com o conteúdo dos PDFs anexados (PGR e PCMSO). Seja técnico, objetivo e rigoroso. Para cada ressalva:
- Indique se é procedente, parcialmente procedente ou improcedente.
- Fundamente a conclusão citando trechos e requisitos aplicáveis das NRs indicadas.
- Aponte exatamente qual parte do PGR/PCMSO (se aplicável) necessita ajuste, e descreva a correção técnica necessária.
- Gere um Parecer Técnico de Contestação bem estruturado (resumo executivo, fundamentos técnicos, conclusão).
- Se for necessário ajustar ou gerar algum apêndice/documento (ex.: inventário de agentes, plano de ação, mapa de risco, formulário), gere o código HTML5/CSS3 completo do Apêndice/Documento entre tags ```html ... ``` seguindo boas práticas de HTML sem depender de frameworks externos. O HTML deve ser pronto para conversão direta para PDF.

Dados:
- Arquivos PGR e PCMSO: enviados como anexos (identifique-os como PGR e PCMSO)
- Ressalvas da auditoria:
{ressalvas_text}

Regras adicionais:
- Sempre justifique com referência às NRs (NR-01, NR-07, NR-17, NR-20, NR-35).
- Quando gerar HTML, inclua título, cabeçalho com identificação da empresa, seções e tabelas necessárias, e um rodapé com data.
- Caso não haja necessidade de gerar HTML, não inclua nenhuma tag ```html``` na resposta.
- Responda em português do Brasil.

Anexos enviados (metadados):
- PGR: {getattr(uploaded['pgr'], 'name', uploaded['pgr'])}
- PCMSO: {getattr(uploaded['pcmsop'], 'name', uploaded['pcmsop'])}
"""

            # Chamada à API Responses de GenAI
            try:
                response = client.responses.create(
                    model="gemini-2.5-pro",
                    temperature=0.0,
                    max_output_tokens=3500,
                    input=prompt
                )
                # extrai texto do response de forma genérica
                ai_text = ""
                if hasattr(response, "output"):
                    # alguns SDK retornam response.output[0].content[0].text
                    try:
                        # tentativa de vários caminhos
                        if isinstance(response.output, list):
                            for item in response.output:
                                if isinstance(item, dict) and "content" in item:
                                    for c in item["content"]:
                                        if isinstance(c, dict) and c.get("type") == "output_text":
                                            ai_text += c.get("text", "")
                                        elif isinstance(c, str):
                                            ai_text += c
                        elif isinstance(response.output, str):
                            ai_text = response.output
                    except Exception:
                        ai_text = str(response.output)
                else:
                    # fallback
                    ai_text = getattr(response, "text", None) or str(response)

            except Exception as e:
                st.error(f"Erro ao solicitar análise ao Gemini: {e}")
                raise

            # Exibir Parecer Técnico
            with output_container:
                st.subheader("Parecer Técnico de Contestação")
                st.write(ai_text)

                # Extrair HTML se houver
                html_code = extract_html_from_text(ai_text)
                if html_code:
                    st.success("HTML de apêndice/documento detectado. Gerando PDF...")
                    try:
                        pdf_bytes = HTML(string=html_code).write_pdf()
                        st.download_button("Download do PDF do Apêndice/Documento (WeasyPrint)", data=pdf_bytes, file_name="apendice_documento.pdf", mime="application/pdf")
                        st.markdown("Visualização do HTML gerado:")
                        st.components.v1.html(html_code, height=600, scrolling=True)
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF do HTML: {e}")
                else:
                    st.info("Nenhum HTML detectado na resposta do modelo.")

            # Limpeza de arquivos locais - tente remover os temporários
            try:
                os.unlink(pgr_path)
                os.unlink(pcmsop_path)
            except Exception:
                pass

            # NOTA: remoção do arquivo na API do GenAI dependerá da API/SDK. Caso exista método de exclusão, recomenda-se chamar aqui.
            st.success("Processo concluído.")
