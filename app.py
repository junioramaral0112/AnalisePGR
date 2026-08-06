import os
from google import genai
from google.genai import types
import weasyprint

# 1. Configurar a chave de API do Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def processar_auditoria_sst(caminho_pgr, caminho_pcmso, texto_ressalva):
    print("Enviando documentos para análise da IA...")
    
    # Faz o upload dos arquivos PDF para a API do Gemini
    file_pgr = client.files.upload(file=caminho_pgr)
    file_pcmso = client.files.upload(file=caminho_pcmso)

    prompt = f"""
    Você é um Engenheiro de Segurança do Trabalho e Médico do Trabalho Especialista em Auditorias de SST (NR-01, NR-07, NR-17, eSocial).

    Sua tarefa é analisar as RESSALVAS/INCONSISTÊNCIAS apontadas pela auditoria de terceiros e confrontá-las com os documentos anexados (PGR e PCMSO).

    TEXTO DAS RESSALVAS:
    {texto_ressalva}

    DIRETRIZES DE SAÍDA:
    1. Se as ressalvas forem IMPROCEDENTES (ou seja, o PGR/PCMSO já atende), gere um PARECER TÉCNICO DE CONTESTAÇÃO fundamentado citando os itens do documento.
    2. Se a ressalva exigir um novo documento/Apêndice corrigido, gere o PARECER TÉCNICO e, ao final, forneça o código HTML5/CSS3 completo do Apêndice/Documento pronto para impressão A4.
    3. Se houver código HTML gerado, coloque-o estritamente entre as tags ```html e ```.
    """

    # Chamada para o modelo
    response = client.models.generate_content(
        model='gemini-2.5-pro',
        contents=[file_pgr, file_pcmso, prompt]
    )

    conteudo_resposta = response.text
    print("\n--- RESPOSTA DA IA ---")
    print(conteudo_resposta)

    # Verifica se a IA gerou um HTML para conversão em PDF
    if "```html" in conteudo_resposta:
        html_code = conteudo_resposta.split("```html")[1].split("```")[0].strip()
        
        # Salva o arquivo HTML
        with open("Apendice_Corrigido.html", "w", encoding="utf-8") as f:
            f.write(html_code)
            
        # Converte o HTML diretamente em PDF
        weasyprint.HTML(string=html_code).write_pdf("Apendice_Corrigido.pdf")
        print("\n✅ Sucesso! O arquivo 'Apendice_Corrigido.pdf' foi gerado automaticamente.")

# Exemplo de uso:
if __name__ == "__main__":
    pgr_path = "PGR FEMSA SC 2026 Rev 01.pdf"
    pcmso_path = "PCMSO FEMSA SC 2026 Rev 01.pdf"
    ressalvas = """
    Existem 1 ressalvas neste documento: os riscos psicossociais não constam no Inventário de Riscos Ocupacionais.
    """

    processar_auditoria_sst(pgr_path, pcmso_path, ressalvas)
