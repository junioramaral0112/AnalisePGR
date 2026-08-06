import io
import os
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from openai import OpenAI
from pypdf import PdfReader
import streamlit as st

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Sistema de Contestação e Ajustes de SST",
    page_icon="🛡️",
    layout="wide",
)

# Inicializa o session_state para manter a tela e os downloads fixos
if "docx_parecer" not in st.session_state:
    st.session_state.docx_parecer = None
if "docx_apendice" not in st.session_state:
    st.session_state.docx_apendice = None
if "texto_parecer" not in st.session_state:
    st.session_state.texto_parecer = None
if "texto_apendice" not in st.session_state:
    st.session_state.texto_apendice = None


# Extração de texto dos PDFs
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


# Converte texto estruturado em formato Word (.docx) com suporte a tabelas
def converter_texto_para_word(texto_markdown, titulo_doc):
    doc = Document()

    # Formatação de Fonte
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    # Título Principal do Arquivo
    p_titulo = doc.add_paragraph()
    p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_titulo = p_titulo.add_run(titulo_doc)
    run_titulo.bold = True
    run_titulo.font.size = Pt(15)
    run_titulo.font.color.rgb = RGBColor(0, 51, 102)

    doc.add_paragraph()

    linhas = texto_markdown.split("\n")
    tabela_atual = None

    for linha in linhas:
        linha_str = linha.strip()
        if not linha_str:
            continue

        # Títulos de seções
        if linha_str.startswith("#"):
            titulo_limpo = linha_str.lstrip("#").strip()
            p_sub = doc.add_paragraph()
            run_sub = p_sub.add_run(titulo_limpo)
            run_sub.bold = True
            run_sub.font.size = Pt(12)
            run_sub.font.color.rgb = RGBColor(0, 102, 153)

        # Montagem de Tabelas em Word
        elif linha_str.startswith("|") and linha_str.endswith("|"):
            colunas = [c.strip() for c in linha_str.split("|")[1:-1]]

            if all(set(c) <= set("-: ") for c in colunas):
                continue

            if tabela_atual is None:
                tabela_atual = doc.add_table(rows=1, cols=len(colunas))
                tabela_atual.style = "Table Grid"
                hdr_cells = tabela_atual.rows[0].cells
                for i, col_texto in enumerate(colunas):
                    hdr_cells[i].text = col_texto
                    for p in hdr_cells[i].paragraphs:
                        for run in p.runs:
                            run.bold = True
            else:
                row_cells = tabela_atual.add_row().cells
                for i, col_texto in enumerate(colunas):
                    if i < len(row_cells):
                        row_cells[i].text = col_texto
        else:
            tabela_atual = None
            p = doc.add_paragraph()
            partes = linha_str.split("**")
            for idx, parte in enumerate(partes):
                run = p.add_run(parte)
                if idx % 2 != 0:
                    run.bold = True

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# Interface
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de Gestão de SST & Auditoria**\n\nGerador de Documentos Word (.docx)"
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

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Documentos em Word")

if btn_analisar:
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
            "⏳ Elaborando o Parecer e o Apêndice em Word com o DeepSeek..."
        ):
            try:
                texto_pgr = extrair_texto_pdf(pgr_file)
                texto_pcmso = extrair_texto_pdf(pcmso_file)

                client = OpenAI(
                    api_key=api_key, base_url="https://api.deepseek.com"
                )

                prompt_completo = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias de SST (NR-01, NR-07, NR-17, eSocial).

                Sua missão é gerar DOIS BLOCOS DE RESPOSTA BEM DELIMITADOS:

                --- CONTEÚDO DO PGR ---
                {texto_pgr[:40000]}

                --- CONTEÚDO DO PCMSO ---
                {texto_pcmso[:40000]}

                --- RESSALVAS DA AUDITORIA ---
                {ressalvas_text}

                ESTRUTURA DA RESPOSTA:
                Utilize a marca === DIVISOR === exatamente para separar o Parecer Técnico do Apêndice.

                [BLOCO 1: PARECER TÉCNICO]
                # PARECER TÉCNICO DE CONTESTAÇÃO DE SST
                (Escreva a resposta e contestação fundamentada na norma).

                === DIVISOR ===

                [BLOCO 2: APÊNDICE A E B]
                # APÊNDICE A – INVENTÁRIO DE RISCOS OCUPACIONAIS CONSOLIDADO
                (Monte a tabela completa Markdown com as colunas: Tipo de Risco | Exposição | Perigo/Fonte Geradora | Resultado | Reconhecido? | Risco/Dano | Avaliação Inicial | Medidas de Controle | Avaliação Residual | eSocial/Plano de Ação. Inclua Riscos Físicos, Químicos, Acidentes, Ergonômicos e Psicossociais).

                # APÊNDICE B – PLANO DE AÇÃO DE SAÚDE MENTAL E RISCOS PSICOSSOCIAIS
                (Monte a tabela do Plano de Ação em formato Markdown).
                """

                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "Você é um gerador de laudos técnicos de SST formatados com delimitador === DIVISOR ===",
                        },
                        {"role": "user", "content": prompt_completo},
                    ],
                    stream=False,
                )

                conteudo_total = response.choices[0].message.content

                # Divide o parecer do apêndice usando o divisor
                if "=== DIVISOR ===" in conteudo_total:
                    partes = conteudo_total.split("=== DIVISOR ===")
                    texto_parecer = partes[0].strip()
                    texto_apendice = partes[1].strip()
                else:
                    texto_parecer = conteudo_total
                    texto_apendice = conteudo_total

                # Gera os dois arquivos Word
                bytes_parecer = converter_texto_para_word(
                    texto_parecer, "PARECER TÉCNICO DE CONTESTAÇÃO DE SST"
                )
                bytes_apendice = converter_texto_para_word(
                    texto_apendice,
                    "APÊNDICE A E B – INVENTÁRIO DE RISCOS E PLANO DE AÇÃO",
                )

                # Salva na memória do Streamlit
                st.session_state.texto_parecer = texto_parecer
                st.session_state.texto_apendice = texto_apendice
                st.session_state.docx_parecer = bytes_parecer
                st.session_state.docx_apendice = bytes_apendice

                st.success(
                    "✅ Parecer Técnico e Apêndice gerados com sucesso em Word!"
                )

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")

# Exibição dos botões fixos de download
if st.session_state.docx_parecer and st.session_state.docx_apendice:
    st.markdown("---")
    st.markdown("### 📥 Baixe os Arquivos Editáveis no Word (.docx)")

    col_w1, col_w2 = st.columns(2)

    with col_w1:
        st.download_button(
            label="📝 Baixar Parecer Técnico (.docx)",
            data=st.session_state.docx_parecer,
            file_name="Parecer_Tecnico_SST.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    with col_w2:
        st.download_button(
            label="📊 Baixar Apêndice A e B (.docx)",
            data=st.session_state.docx_apendice,
            file_name="Apendice_A_e_B_Inventario_Riscos.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    st.markdown("---")
    st.markdown("### 📋 Pré-visualização do Apêndice Gerado")
    st.write(st.session_state.texto_apendice)
