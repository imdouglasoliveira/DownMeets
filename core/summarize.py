"""
Módulo para gerar resumos de transcrições de vídeos do Google Meet.
"""

import os
import logging
from pathlib import Path
from typing import Optional

import openai

logger = logging.getLogger("DownMeets.summarize")


def read_transcription(transcription_path: str) -> Optional[str]:
    """Lê o arquivo de transcrição."""
    try:
        with open(transcription_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.exception(f"Erro ao ler arquivo de transcrição: {str(e)}")
        return None


def generate_summary_with_openai(
    transcription: str,
    model: str,
    language: str,
    api_key: str
) -> Optional[str]:
    """
    Gera um resumo de uma transcrição usando a API GPT da OpenAI.
    Retorna o resumo se bem-sucedido, None caso contrário.
    """
    try:
        # Configurar a chave da API
        openai.api_key = api_key
        
        # Criar a mensagem para a API
        prompt = f"""
        Você é um especialista em resumir reuniões e criar notas de reunião.
        Abaixo está a transcrição de uma reunião do Google Meet.
        Por favor, gere um resumo estruturado que inclua:

        1. Principais tópicos discutidos
        2. Decisões tomadas
        3. Tarefas atribuídas (com responsáveis, se mencionados)
        4. Pontos importantes a serem lembrados
        5. Próximos passos

        O resumo deve ser claro, conciso e em formato markdown.
        Idioma do resumo: {language}

        Transcrição:
        {transcription}
        """
        
        # Chamar a API para gerar o resumo
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em resumir reuniões e criar notas de reunião."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=4000
        )
        
        # Extrair o resumo da resposta
        if (
            hasattr(response, "choices") and 
            len(response.choices) > 0 and 
            hasattr(response.choices[0], "message") and 
            hasattr(response.choices[0].message, "content")
        ):
            return response.choices[0].message.content
        elif isinstance(response, dict) and "choices" in response:
            return response["choices"][0]["message"]["content"]
        else:
            logger.error(f"Resposta inesperada da API: {response}")
            return None
            
    except Exception as e:
        logger.exception(f"Erro ao gerar resumo com OpenAI: {str(e)}")
        return None


def generate_summary(
    transcription_path: str,
    output_path: str,
    model: str,
    language: str,
    api_key: str
) -> bool:
    """
    Gera um resumo de uma transcrição e salva em um arquivo markdown.
    Retorna True se bem-sucedido, False caso contrário.
    """
    try:
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Ler a transcrição
        transcription = read_transcription(transcription_path)
        
        if transcription is None:
            logger.error(f"Falha ao ler o arquivo de transcrição: {transcription_path}")
            return False
        
        # Gerar o resumo
        logger.info(f"Gerando resumo para: {transcription_path}")
        summary = generate_summary_with_openai(transcription, model, language, api_key)
        
        if summary is None:
            logger.error("Falha ao gerar resumo")
            return False
        
        # Salvar o resumo
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(summary)
        
        logger.info(f"Resumo salvo em: {output_path}")
        return True
        
    except Exception as e:
        logger.exception(f"Erro ao gerar resumo: {str(e)}")
        return False