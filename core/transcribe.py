"""
Módulo para transcrever vídeos do Google Meet.
"""

import os
import logging
import tempfile
import subprocess
import math
from pathlib import Path
from typing import Optional, List

from openai import OpenAI

logger = logging.getLogger("DownMeets.transcribe")

# Limite de tamanho para a API Whisper (em MB)
MAX_AUDIO_SIZE_MB = 25


def extract_audio(video_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Extrai o áudio de um vídeo usando ffmpeg.
    Retorna o caminho do arquivo de áudio extraído.
    """
    try:
        if output_path is None:
            # Criar um arquivo temporário para o áudio
            fd, output_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

        # Comando ffmpeg para extrair o áudio
        command = [
            "ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", output_path, "-y"
        ]
        
        # Executar o comando
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if process.returncode != 0:
            logger.error(f"Erro ao extrair áudio: {process.stderr}")
            return None
        
        # Verificar se o arquivo foi criado e tem conteúdo
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
        else:
            logger.error("Arquivo de áudio extraído está vazio ou não existe")
            return None
            
    except Exception as e:
        logger.exception(f"Erro ao extrair áudio do vídeo: {str(e)}")
        return None


def get_audio_duration(audio_path: str) -> Optional[float]:
    """Obtém a duração de um arquivo de áudio em segundos usando ffprobe."""
    try:
        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if process.returncode != 0:
            logger.error(f"Erro ao obter duração do áudio: {process.stderr}")
            return None
        
        return float(process.stdout.strip())
        
    except Exception as e:
        logger.exception(f"Erro ao obter duração do áudio: {str(e)}")
        return None


def split_audio_with_ffmpeg(audio_path: str, max_size_mb: int = MAX_AUDIO_SIZE_MB) -> List[str]:
    """
    Divide um arquivo de áudio em segmentos menores usando ffmpeg.
    Retorna uma lista de caminhos para os arquivos de áudio resultantes.
    """
    try:
        # Verificar o tamanho do arquivo
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        
        if file_size_mb <= max_size_mb:
            # Se o arquivo for pequeno o suficiente, retornar o caminho original
            return [audio_path]
        
        # Obter a duração do áudio
        duration = get_audio_duration(audio_path)
        if duration is None:
            logger.warning("Não foi possível obter a duração do áudio. Usando o arquivo original.")
            return [audio_path]
        
        # Estimar quantas partes são necessárias (relação aproximada entre tamanho e duração)
        num_parts = math.ceil(file_size_mb / max_size_mb)
        segment_duration = math.ceil(duration / num_parts)
        
        # Diretório para armazenar os segmentos
        temp_dir = tempfile.mkdtemp()
        segments = []
        
        for i in range(num_parts):
            start_time = i * segment_duration
            output_segment = os.path.join(temp_dir, f"segment_{i}.mp3")
            
            # Comando para extrair o segmento
            command = [
                "ffmpeg",
                "-i", audio_path,
                "-ss", str(start_time),
                "-t", str(segment_duration),
                "-acodec", "copy",
                output_segment,
                "-y"
            ]
            
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if process.returncode != 0:
                logger.error(f"Erro ao dividir áudio (segmento {i}): {process.stderr}")
                continue
                
            if os.path.exists(output_segment) and os.path.getsize(output_segment) > 0:
                segments.append(output_segment)
            
        if not segments:
            logger.warning("Não foi possível dividir o áudio. Usando o arquivo original.")
            return [audio_path]
            
        logger.info(f"Áudio dividido em {len(segments)} segmentos")
        return segments
        
    except Exception as e:
        logger.exception(f"Erro ao dividir áudio: {str(e)}")
        return [audio_path]


def transcribe_with_openai(audio_path: str, model: str, api_key: str) -> Optional[str]:
    """
    Transcreve um arquivo de áudio usando a API Whisper da OpenAI.
    Atualizado para usar a nova API OpenAI (1.0.0+).
    Retorna o texto transcrito se bem-sucedido, None caso contrário.
    """
    try:
        # Inicializar o cliente OpenAI com a chave da API
        client = OpenAI(api_key=api_key)
        
        # Abrir o arquivo de áudio
        with open(audio_path, "rb") as audio_file:
            # Chamar a API de transcrição com a nova sintaxe
            response = client.audio.transcriptions.create(
                model=model,
                file=audio_file
            )
        
        # Extrair o texto transcrito
        if hasattr(response, "text"):
            return response.text
        elif isinstance(response, dict) and "text" in response:
            return response["text"]
        else:
            logger.error(f"Resposta inesperada da API: {response}")
            return None
            
    except Exception as e:
        logger.exception(f"Erro ao transcrever com OpenAI: {str(e)}")
        return None


def transcribe_video(video_path: str, output_path: str, model: str, api_key: str) -> bool:
    """
    Transcreve um vídeo e salva a transcrição em um arquivo de texto.
    Retorna True se bem-sucedido, False caso contrário.
    """
    try:
        if not api_key:
            logger.error("Chave da API OpenAI não fornecida")
            return False
            
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Extrair o áudio do vídeo
        logger.info(f"Extraindo áudio do vídeo: {video_path}")
        audio_path = extract_audio(video_path)
        
        if audio_path is None:
            logger.error("Falha ao extrair áudio do vídeo")
            return False
        
        # Verificar o tamanho do arquivo de áudio
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logger.info(f"Tamanho do arquivo de áudio: {file_size_mb:.2f} MB")
        
        # Dividir o áudio em segmentos se necessário
        audio_segments = split_audio_with_ffmpeg(audio_path)
        
        # Transcrever cada segmento
        full_transcription = ""
        for i, segment_path in enumerate(audio_segments):
            logger.info(f"Transcrevendo segmento {i+1}/{len(audio_segments)}")
            segment_transcription = transcribe_with_openai(segment_path, model, api_key)
            
            if segment_transcription is None:
                logger.error(f"Falha ao transcrever segmento {i+1}")
                continue
            
            # Adicionar a transcrição do segmento ao resultado final
            full_transcription += segment_transcription + "\n\n"
            
            # Remover o arquivo de áudio temporário se for um segmento
            if len(audio_segments) > 1 and segment_path != audio_path:
                try:
                    os.remove(segment_path)
                except Exception as e:
                    logger.warning(f"Não foi possível remover o arquivo de áudio temporário: {str(e)}")
        
        # Remover o arquivo de áudio original
        try:
            os.remove(audio_path)
        except Exception as e:
            logger.warning(f"Não foi possível remover o arquivo de áudio original: {str(e)}")
        
        if not full_transcription:
            logger.error("Nenhuma transcrição gerada")
            return False
        
        # Salvar a transcrição
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_transcription)
        
        logger.info(f"Transcrição salva em: {output_path}")
        return True
        
    except Exception as e:
        logger.exception(f"Erro ao transcrever vídeo: {str(e)}")
        return False