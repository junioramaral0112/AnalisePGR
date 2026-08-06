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

# Inicializa a sessão para manter a tela e os downloads fixos
if "docx_bytes" not in st.session_state:
    st.session_state.docx_bytes = None


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


# Converte texto Markdown estruturado em um documento Word (.docx) completo
def converter_markdown_para_word(texto_markdown):
    doc = Document()

    # Configuração global da fonte
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(10)

    linhas = texto_markdown.split("\n")
    tabela_atual = None

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
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(0, 51, 102)

        # Subtítulos (## ou ###)
        elif linha_str.startswith("##"):
            sub_limpo = linha_str.lstrip("#").strip()
            p = doc.add_paragraph()
            run = p.add_run(sub_limpo)
            run.bold = True
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 102, 153)

        # Processamento de Tabelas em Markdown (| Coluna | Coluna |)
        elif linha_str.startswith("|") and linha_str.endswith("|"):
            colunas = [c.strip() for c in linha_str.split("|")[1:-1]]

            # Descarta linhas separadoras (|---|---|)
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
                            run.font.size = Pt(9)
            else:
                row_cells = tabela_atual.add_row().cells
                for i, col_texto in enumerate(colunas):
                    if i < len(row_cells):
                        row_cells[i].text = col_texto
                        for p in row_cells[i].paragraphs:
                            for run in p.runs:
                                run.font.size = Pt(9)
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


# Interface
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
                Forneça a TABELA MARKDOWN COMPLETA preenchendo detalhadamente as 9 colunas para todos os riscos encontrados no PGR/PCMSO, INCLUINDO OS RISCOS PSICOSSOCIAIS:
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

                # Converte todo o texto e tabelas para o formato Word
                bytes_word = converter_markdown_para_word(texto_resposta)

                # Grava na sessão para manter o botão fixo
                st.session_state.docx_bytes = bytes_word

                st.success(
                    "✅ Relatório e Apêndice gerados com sucesso no Word!"
                )

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")

# Exibe o botão de download persistente (sem resetar a página)
if st.session_state.docx_bytes:
    st.markdown("---")
    st.markdown("### 📥 Baixar Relatório Completo em Word")

    st.download_button(
        label="📝 Baixar Parecer Técnico + Apêndice A e B (.docx)",
        data=st.session_state.docx_bytes,
        file_name="Parecer_e_Apendice_SST_Completo.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
