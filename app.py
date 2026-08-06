import io
import os
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from openai import OpenAI
from pypdf import PdfReader
import streamlit as st

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Sistema de Contestação e Ajustes de SST",
    page_icon="🛡️",
    layout="wide",
)

# Inicializa o session_state para manter o download fixo na tela
if "docx_bytes" not in st.session_state:
    st.session_state.docx_bytes = None
if "texto_parecer" not in st.session_state:
    st.session_state.texto_parecer = None


# Função para extrair texto dos PDFs enviados
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


# Função para converter o texto em um documento Word (.docx) formatado
def criar_documento_word(texto_parecer):
    doc = Document()

    # Estilo geral do documento
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)

    # Título Principal
    p_titulo = doc.add_paragraph()
    p_titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_titulo = p_titulo.add_run(
        "PARECER TÉCNICO DE CONTESTAÇÃO E APÊNDICE DE SST"
    )
    run_titulo.bold = True
    run_titulo.font.size = Pt(16)
    run_titulo.font.color.rgb = RGBColor(0, 51, 102)

    doc.add_paragraph()  # Espaço

    # Processa o texto linha por linha para formatar títulos, listas e tabelas
    linhas = texto_parecer.split("\n")
    tabela_atual = None

    for linha in linhas:
        linha_str = linha.strip()

        if not linha_str:
            continue

        # Títulos de Seções (ex: # 1. Objeto, ## Apêndice A)
        if linha_str.startswith("#"):
            titulo_limpo = linha_str.lstrip("#").strip()
            p_sub = doc.add_paragraph()
            run_sub = p_sub.add_run(titulo_limpo)
            run_sub.bold = True
            run_sub.font.size = Pt(13)
            run_sub.font.color.rgb = RGBColor(0, 102, 153)

        # Trata linhas de tabelas Markdown (| Coluna 1 | Coluna 2 |)
        elif linha_str.startswith("|") and linha_str.endswith("|"):
            colunas = [c.strip() for c in linha_str.split("|")[1:-1]]

            # Ignora linha separadora do markdown (|---|---|)
            if all(set(c) <= set("-: ") for c in colunas):
                continue

            # Se for o início de uma nova tabela
            if tabela_atual is None:
                tabela_atual = doc.add_table(rows=1, cols=len(colunas))
                tabela_atual.style = "Table Grid"
                hdr_cells = tabela_atual.rows[0].cells
                for i, col_texto in enumerate(colunas):
                    hdr_cells[i].text = col_texto
                    # Deixa o cabeçalho em negrito
                    for paragraph in hdr_cells[i].paragraphs:
                        for run in paragraph.runs:
                            run.bold = True
            else:
                row_cells = tabela_atual.add_row().cells
                for i, col_texto in enumerate(colunas):
                    if i < len(row_cells):
                        row_cells[i].text = col_texto
        else:
            # Reseta o ponteiro da tabela ao voltar a ser texto normal
            tabela_atual = None

            # Linha comum de parágrafo
            p = doc.add_paragraph()
            # Trata negritos simples em markdown (**texto**)
            partes = linha_str.split("**")
            for idx, parte in enumerate(partes):
                run = p.add_run(parte)
                if idx % 2 != 0:  # Parte ímpar estava entre ** **
                    run.bold = True

    # Salva o arquivo Word em um buffer de memória de bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# Interface
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de Gestão de SST & Auditoria**\n\nGerador de Documentos Word (.docx) via **DeepSeek API**."
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

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Parecer em Word")

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
            "⏳ Lendo documentos e gerando relatório técnico com o DeepSeek..."
        ):
            try:
                texto_pgr = extrair_texto_pdf(pgr_file)
                texto_pcmso = extrair_texto_pdf(pcmso_file)

                client = OpenAI(
                    api_key=api_key, base_url="https://api.deepseek.com"
                )

                prompt_completo = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias de SST (NR-01, NR-07, NR-17, eSocial).

                Sua missão é emitir o PARECER TÉCNICO DE CONTESTAÇÃO DE SST e o APÊNDICE A (Inventário de Riscos Ocupacionais Consolidado) e APÊNDICE B (Plano de Ação).

                --- CONTEÚDO DO PGR ---
                {texto_pgr[:40000]}

                --- CONTEÚDO DO PCMSO ---
                {texto_pcmso[:40000]}

                --- RESSALVAS DA AUDITORIA ---
                {ressalvas_text}

                DIRETRIZES DE FORMATAÇÃO:
                1. Escreva o Parecer Técnico completo fundamentado na legislação.
                2. Monte as tabelas do Apêndice A (com riscos Físicos, Químicos, Acidentes, Ergonômicos e Psicossociais) e Apêndice B usando o formato padrão de Tabela Markdown (| Coluna 1 | Coluna 2 | Coluna 3 |).
                3. Utilize títulos Markdown (# Seção, ## Subseção) e negrito (**texto**) para estruturar o documento.
                """

                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "Você é um gerador de laudos e pareceres técnicos de SST.",
                        },
                        {"role": "user", "content": prompt_completo},
                    ],
                    stream=False,
                )

                texto_resposta = response.choices[0].message.content

                # Converte a resposta estruturada em arquivo Word
                bytes_word = criar_documento_word(texto_resposta)

                # Salva na sessão para manter a tela fixa
                st.session_state.texto_parecer = texto_resposta
                st.session_state.docx_bytes = bytes_word

                st.success("✅ Parecer e Apêndice gerados com sucesso!")

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")

# Exibe o resultado e o botão de download persistente
if st.session_state.docx_bytes:
    st.markdown("---")
    st.markdown("### 📥 Baixar Documento Editável")

    st.download_button(
        label="📝 Baixar Parecer e Apêndice no Word (.docx)",
        data=st.session_state.docx_bytes,
        file_name="Parecer_e_Apendice_SST.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    st.markdown("---")
    st.markdown("### 📋 Conteúdo Gerado")
    st.write(st.session_state.texto_parecer)
