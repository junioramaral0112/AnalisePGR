import io
import os
import re
from google import genai
from google.genai import types
import streamlit as st
from xhtml2pdf import pisa

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Sistema de Contestação e Ajustes de SST",
    page_icon="🛡️",
    layout="wide",
)


# Função para converter HTML em PDF usando xhtml2pdf (Python Puro)
def converter_html_para_pdf(html_code):
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=io.StringIO(html_code), dest=pdf_buffer)
    if pisa_status.err:
        return None
    return pdf_buffer.getvalue()


# Barra Lateral - Configurações
st.sidebar.title("⚙️ Configurações")
api_key = st.sidebar.text_input(
    "Insira sua GEMINI_API_KEY:",
    value=os.environ.get("GEMINI_API_KEY", ""),
    type="password",
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Sistema de Gestão de Auditoria de SST**\n\n"
    "Análise automatizada de ressalvas de PGR e PCMSO integrada com a nova regulamentação de Riscos Psicossociais (NR-01, NR-07, NR-17)."
)

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
    if not api_key:
        st.error(
            "⚠️ Por favor, insira uma chave de API do Gemini válida na barra lateral!"
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
                # Inicializa o cliente oficial do Google GenAI
                client = genai.Client(api_key=api_key)

                # Salva arquivos temporariamente para upload na API
                with open("temp_pgr.pdf", "wb") as f:
                    f.write(pgr_file.getbuffer())

                with open("temp_pcmso.pdf", "wb") as f:
                    f.write(pcmso_file.getbuffer())

                # Upload dos PDFs para a API Gemini
                up_pgr = client.files.upload(file="temp_pgr.pdf")
                up_pcmso = client.files.upload(file="temp_pcmso.pdf")

                # Prompt especializado para SST
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

                # Executa a geração de conteúdo
                response = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=[up_pgr, up_pcmso, prompt_sistema],
                )

                resultado_texto = response.text

                # Exibe o parecer técnico na tela
                st.success("✅ Análise concluída com sucesso!")
                st.markdown("### 📋 Parecer Técnico e Análise de Conformidade")
                st.write(resultado_texto)

                # Verifica se há código HTML na resposta para conversão em PDF
                if "```html" in resultado_texto:
                    html_code = (
                        resultado_texto.split("```html")[1]
                        .split("```")[0]
                        .strip()
                    )

                    # Gera o PDF via xhtml2pdf
                    pdf_bytes = converter_html_para_pdf(html_code)

                    if pdf_bytes:
                        st.markdown("---")
                        st.markdown("### 📥 Documento / Apêndice Gerado")
                        st.download_button(
                            label="📄 Baixar Apêndice/Documento Corrigido em PDF",
                            data=pdf_bytes,
                            file_name="Apendice_Corrigido_SST.pdf",
                            mime="application/pdf",
                        )
                    else:
                        st.warning(
                            "Ocorreu um erro ao converter o HTML para PDF."
                        )

                # Limpeza de arquivos temporários locais e na nuvem do Gemini
                os.remove("temp_pgr.pdf")
                os.remove("temp_pcmso.pdf")
                client.files.delete(name=up_pgr.name)
                client.files.delete(name=up_pcmso.name)

            except Exception as e:
                st.error(f"❌ Ocorreu um erro durante o processamento: {str(e)}")
