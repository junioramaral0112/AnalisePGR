import io
import os
from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
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

# Inicializa o session_state para manter a tela e os downloads fixos
if "docx_bytes" not in st.session_state:
    st.session_state.docx_bytes = None
if "texto_resposta" not in st.session_state:
    st.session_state.texto_resposta = None


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


# Função auxiliar para aplicar cor de fundo em células do Word
def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


# Converte texto Markdown em um documento Word (.docx) formatado em Paisagem com tabelas coloridas
def converter_markdown_para_word_paisagem(texto_markdown):
    doc = Document()

    # 1. Configura a página para A4 PAISAGEM (Landscape)
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    # Inverte as dimensões A4 (29,7 cm x 21,0 cm)
    new_width, new_height = section.page_height, section.page_width
    section.page_width = new_width
    section.page_height = new_height
    section.top_margin = Inches(0.5)
    section.bottom_margin = Inches(0.5)
    section.left_margin = Inches(0.5)
    section.right_margin = Inches(0.5)

    # Configuração global de fonte
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(9.5)

    linhas = texto_markdown.split("\n")
    tabela_atual = None
    row_count = 0

    for linha in linhas:
        linha_str = linha.strip()
        if not linha_str:
            continue

        # Título Principal (#)
        if linha_str.startswith("# "):
            titulo_limpo = linha_str.replace("# ", "").strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(titulo_limpo)
            run.bold = True
            run.font.size = Pt(15)
            run.font.color.rgb = RGBColor(0, 51, 102)

        # Subtítulos (## ou ###)
        elif linha_str.startswith("##"):
            sub_limpo = linha_str.lstrip("#").strip()
            p = doc.add_paragraph()
            run = p.add_run(sub_limpo)
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 102, 153)

        # Processamento de Tabelas (| Coluna | Coluna |)
        elif linha_str.startswith("|") and linha_str.endswith("|"):
            colunas = [c.strip() for c in linha_str.split("|")[1:-1]]

            # Descarta linhas separadoras (|---|---|)
            if all(set(c) <= set("-: ") for c in colunas):
                continue

            # Início de uma nova tabela
            if tabela_atual is None:
                row_count = 0
                tabela_atual = doc.add_table(rows=1, cols=len(colunas))
                tabela_atual.style = "Table Grid"

                # Formata Cabeçalho: Fundo Azul Escuro (003366) e Texto Branco/Negrito
                hdr_cells = tabela_atual.rows[0].cells
                for i, col_texto in enumerate(colunas):
                    hdr_cells[i].text = col_texto
                    set_cell_background(hdr_cells[i], "003366")
                    for p in hdr_cells[i].paragraphs:
                        for run in p.runs:
                            run.bold = True
                            run.font.size = Pt(9)
                            run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                row_count += 1
                row_cells = tabela_atual.add_row().cells

                # Efeito Zebrado: linhas pares com fundo suave (F2F4F8)
                cor_fundo = "F2F4F8" if row_count % 2 == 0 else "FFFFFF"

                for i, col_texto in enumerate(colunas):
                    if i < len(row_cells):
                        row_cells[i].text = col_texto
                        set_cell_background(row_cells[i], cor_fundo)
                        for p in row_cells[i].paragraphs:
                            for run in p.runs:
                                run.font.size = Pt(8.5)
        else:
            tabela_atual = None
            p = doc.add_paragraph()

            # Trata negritos (**texto**)
            partes = linha_str.split("**")
            for idx, parte in enumerate(partes):
                run = p.add_run(parte)
                if idx % 2 != 0:
                    run.bold = True

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# Interface do Usuário
st.sidebar.title("⚙️ Painel do Sistema")
st.sidebar.info(
    "**Sistema de Gestão de SST & Auditoria**\n\nMotor de IA: **DeepSeek API**"
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

btn_analisar = st.button("🚀 Analisar Ressalvas e Gerar Documento Completo")

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
            "⏳ Processando documentos e montando o relatório técnico em Word..."
        ):
            try:
                texto_pgr = extrair_texto_pdf(pgr_file)
                texto_pcmso = extrair_texto_pdf(pcmso_file)

                client = OpenAI(
                    api_key=api_key, base_url="https://api.deepseek.com"
                )

                prompt_completo = f"""
                Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Sênior, especialista em Auditorias e Conformidade Normativa de SST (NR-01, NR-07, NR-17, eSocial).

                Sua missão é emitir um ÚNICO DOCUMENTO COMPLETO contendo o Parecer Técnico e a revisão integral dos Apêndices A e B.

                --- CONTEÚDO DO PGR ---
                {texto_pgr[:40000]}

                --- CONTEÚDO DO PCMSO ---
                {texto_pcmso[:40000]}

                --- RESSALVAS DA AUDITORIA ---
                {ressalvas_text}

                ESTRUTURA OBRIGATÓRIA DO DOCUMENTO:

                # PARECER TÉCNICO DE CONTESTAÇÃO DE SST
                1. **Objeto e Finalidade:** Descrição completa dos documentos auditados.
                2. **Análise Crítica das Ressalvas:** Parecer detalhado se é Procedente ou Improcedente para cada ressalva informada.
                3. **Fundamentação Legal:** Citar NR-01, NR-07, NR-17 e regras de transição.

                ## APÊNDICE A – INVENTÁRIO DE RISCOS OCUPACIONAIS CONSOLIDADO
                Forneça a TABELA MARKDOWN COMPLETA preenchendo detalhadamente as 10 colunas para todos os riscos encontrados no PGR/PCMSO, INCLUINDO OS RISCOS PSICOSSOCIAIS:
                | Tipo de Risco | Exposição | Perigo / Fonte Geradora | Resultado da Avaliação | Reconhecido? | Risco Ocupacional / Dano | Avaliação Inicial (P x S) | Medidas de Controle / EPIs / EPCs | Avaliação Residual (P x S) | eSocial / Plano de Ação |

                ## APÊNDICE B – PLANO DE AÇÃO DE SAÚDE MENTAL E RISCOS PSICOSSOCIAIS
                Forneça a TABELA MARKDOWN do Plano de Ação detalhada:
                | Ação Preventiva / Corretiva | Fator de Risco | Responsável | Prazo | Indicador de Acompanhamento |
                """

                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "Você é um especialista em elaboração de laudos de SST e tabelas técnicas em Markdown.",
                        },
                        {"role": "user", "content": prompt_completo},
                    ],
                    stream=False,
                )

                texto_resposta = response.choices[0].message.content

                # Converte o relatório formatado em Word Paisagem com Tabelas Coloridas
                bytes_word = converter_markdown_para_word_paisagem(
                    texto_resposta
                )

                # Grava no session_state para manter o estado e os botões ativos
                st.session_state.texto_resposta = texto_resposta
                st.session_state.docx_bytes = bytes_word

                st.success(
                    "✅ Relatório e Apêndice gerados com sucesso no Word!"
                )

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")

# Área fixa de Download e Pré-visualização
if st.session_state.docx_bytes and st.session_state.texto_resposta:
    st.markdown("---")
    st.markdown("### 📥 Baixar Relatório Formatado em Word")

    st.download_button(
        label="📝 Baixar Parecer Técnico + Apêndice A e B (.docx - Paisagem)",
        data=st.session_state.docx_bytes,
        file_name="Parecer_e_Apendice_SST_Paisagem.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    st.markdown("---")
    st.markdown("### 📋 Pré-visualização do Relatório Gerado")
    st.write(st.session_state.texto_resposta)
